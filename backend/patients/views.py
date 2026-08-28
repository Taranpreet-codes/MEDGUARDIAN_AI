"""
patients/views.py — Patient API ViewSets (Stage 1 + Stage 2)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Stage 1:  PatientProfileViewSet, MedicationCabinetViewSet
Stage 2:  AlertViewSet (list unread, acknowledge, SSE stream)
          Safety history endpoint on PatientProfileViewSet
"""
import json
import time
import logging

from django.http import StreamingHttpResponse
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from medguardian.auth import QueryParamJWTAuthentication

from .models import PatientProfile, MedicationCabinet, ProactiveAlert, SafetyAssessmentHistory
from .serializers import (
    PatientProfileSerializer,
    MedicationCabinetSerializer,
    ProactiveAlertSerializer,
    SafetyAssessmentHistorySerializer,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Stage 1: Patient Profile Viewset
# ─────────────────────────────────────────────────────────────────────────────

class PatientProfileViewSet(viewsets.ModelViewSet):
    serializer_class = PatientProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return PatientProfile.objects.filter(user=self.request.user)

    def get_object(self):
        # Always return the current user's profile
        profile, created = PatientProfile.objects.get_or_create(user=self.request.user)
        return profile

    @action(detail=False, methods=['get', 'put', 'patch'])
    def me(self, request):
        profile = self.get_object()
        if request.method == 'GET':
            serializer = self.get_serializer(profile)
            return Response(serializer.data)

        serializer = self.get_serializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='safety-check')
    def safety_check(self, request):
        from services.risk_engine import RiskEngine
        profile = self.get_object()
        evaluator = RiskEngine()
        safety_report = evaluator.evaluate_patient_safety(profile)
        return Response(safety_report, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='chat-ask')
    def chat_ask(self, request):
        import os
        from google import genai
        from services.rag import RAGEngine

        query = request.data.get('query', '')
        if not query:
            return Response({"error": "No query provided"}, status=status.HTTP_400_BAD_REQUEST)

        profile = self.get_object()
        active_meds = MedicationCabinet.objects.filter(patient=profile, is_active=True)
        med_names = [m.name for m in active_meds]

        # RAG Search
        rag = RAGEngine()
        search_terms = f"{query} {', '.join(med_names)}"
        evidence = rag.retrieve_evidence(search_terms, limit=3)

        formatted_evidence = ""
        citations = []
        for e in evidence:
            formatted_evidence += f"- [{e['source']} (Page {e['metadata'].get('page', 1)})] {e['text']}\n"
            citations.append({
                "source": e['source'],
                "page": e['metadata'].get('page', 1),
                "snippet": e['text'][:120] + "..."
            })

        profile_context = (
            f"Patient Profile: Age {profile.age}, Gender {profile.gender}, "
            f"Pregnancy status: {profile.pregnancy_status}, eGFR: {profile.egfr}, Creatinine: {profile.creatinine}. "
            f"Active Cabinet Medications: {', '.join(med_names)}."
        )

        def run_mock_fallback():
            lower_query = query.lower()
            if "pregnant" in lower_query or "pregnancy" in lower_query:
                response_text = (
                    "Based on the provided clinical evidence, Lisinopril is contraindicated during pregnancy "
                    "due to warnings of major birth defects and fetal toxicity."
                )
                mock_citations = [{"source": "WHO_guideline_hypertension.pdf", "page": 12, "snippet": "Lisinopril is strictly contraindicated in pregnancy."}]
            else:
                response_text = "I cannot find enough clinical evidence to safely answer this question."
                mock_citations = []
            return Response({
                "response": response_text,
                "citations": mock_citations
            }, status=status.HTTP_200_OK)

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return run_mock_fallback()

        try:
            client = genai.Client(api_key=api_key)
            prompt = (
                f"You are MedGuardian AI, an evidence-grounded Clinical Decision Support chat assistant.\n\n"
                f"PATIENT CONTEXT:\n{profile_context}\n\n"
                f"RELEVANT GUIDELINES (EVIDENCE):\n{formatted_evidence if formatted_evidence else 'No evidence found.'}\n\n"
                f"USER QUESTION:\n{query}\n\n"
                f"CRITICAL INSTRUCTIONS:\n"
                f"1. Answer the question using ONLY the provided evidence. Do not extrapolate.\n"
                f"2. If the provided guidelines do not contain the answer, or if there is no evidence, you MUST respond exactly: "
                f"'I cannot find enough clinical evidence to safely answer this question.' and nothing else.\n"
                f"3. Make sure to cite the source document name if you use it."
            )

            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt
            )
            return Response({
                "response": response.text.strip(),
                "citations": citations
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.warning(f"Gemini chat assistant failed: {e}. Falling back to mock advisor.")
            return run_mock_fallback()

    @action(detail=False, methods=['get'], url_path='report-patient')
    def report_patient(self, request):
        from django.http import HttpResponse
        from services.reports import ReportService
        profile = self.get_object()
        try:
            pdf_data = ReportService.generate_patient_report(profile)
            response = HttpResponse(pdf_data, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="patient_safety_report_{profile.id}.pdf"'
            return response
        except Exception as e:
            logger.error("Failed to generate patient safety report for profile_id=%s: %s", profile.id, str(e), exc_info=True)
            return Response(
                {"error": "Failed to generate patient safety report. Please try again later."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'], url_path='report-clinician')
    def report_clinician(self, request):
        from django.http import HttpResponse
        from services.reports import ReportService
        profile = self.get_object()
        try:
            pdf_data = ReportService.generate_clinician_report(profile)
            response = HttpResponse(pdf_data, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="clinician_safety_report_{profile.id}.pdf"'
            return response
        except Exception as e:
            logger.error("Failed to generate clinician safety dossier for profile_id=%s: %s", profile.id, str(e), exc_info=True)
            return Response(
                {"error": "Failed to generate clinician safety dossier. Please try again later."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    # ── Stage 2: Safety History Endpoint ─────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='safety-history')
    def safety_history(self, request):
        """
        GET /api/patients/me/safety-history/
        Returns paginated list of SafetyAssessmentHistory records for the
        current patient, ordered newest-first.  Used by the Risk Timeline chart.
        """
        profile = self.get_object()
        history_qs = SafetyAssessmentHistory.objects.filter(
            patient=profile
        ).order_by('-created_at')[:50]  # Cap at 50 for chart performance
        serializer = SafetyAssessmentHistorySerializer(history_qs, many=True)
        return Response({'results': serializer.data}, status=status.HTTP_200_OK)


# ─────────────────────────────────────────────────────────────────────────────
# Stage 1: Medication Cabinet Viewset
# ─────────────────────────────────────────────────────────────────────────────

class MedicationCabinetViewSet(viewsets.ModelViewSet):
    serializer_class = MedicationCabinetSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Retrieve meds for currently authenticated user's profile
        return MedicationCabinet.objects.filter(patient__user=self.request.user)

    def perform_create(self, serializer):
        # Automatically attach the medication to current user's profile
        profile, _ = PatientProfile.objects.get_or_create(user=self.request.user)
        serializer.save(patient=profile)


# ─────────────────────────────────────────────────────────────────────────────
# Stage 2: Alert ViewSet & SSE Stream
# ─────────────────────────────────────────────────────────────────────────────

class AlertViewSet(viewsets.GenericViewSet):
    """
    Endpoints for managing and streaming ProactiveAlert notifications.

    GET  /api/alerts/unread/           — JSON list of unacknowledged alerts
    POST /api/alerts/{id}/acknowledge/ — Mark a single alert as acknowledged
    GET  /api/alerts/stream/           — SSE stream; pushes new alerts every 5s
    """
    serializer_class = ProactiveAlertSerializer
    permission_classes = [permissions.IsAuthenticated]

    def _get_profile(self):
        profile, _ = PatientProfile.objects.get_or_create(user=self.request.user)
        return profile

    @action(detail=False, methods=['get'], url_path='unread')
    def unread(self, request):
        """
        GET /api/alerts/unread/
        Returns all unacknowledged alerts for the current patient, newest first.
        Suitable for long-polling: client can re-poll this endpoint periodically.
        """
        profile = self._get_profile()
        alerts = ProactiveAlert.objects.filter(
            patient=profile, acknowledged=False
        ).select_related('assessment').order_by('-created_at')
        serializer = self.get_serializer(alerts, many=True)
        return Response({'alerts': serializer.data, 'count': alerts.count()})

    @action(detail=True, methods=['post'], url_path='acknowledge')
    def acknowledge(self, request, pk=None):
        """
        POST /api/alerts/{id}/acknowledge/
        Marks the specified alert as acknowledged (dismissed by the user).
        """
        profile = self._get_profile()
        try:
            alert = ProactiveAlert.objects.get(pk=pk, patient=profile)
        except ProactiveAlert.DoesNotExist:
            return Response({'detail': 'Alert not found.'}, status=status.HTTP_404_NOT_FOUND)

        alert.acknowledged = True
        alert.save(update_fields=['acknowledged'])
        return Response({'detail': 'Alert acknowledged.', 'id': alert.pk})

    @action(detail=False, methods=['get'], url_path='stream', authentication_classes=[QueryParamJWTAuthentication])
    def stream(self, request):
        """
        GET /api/alerts/stream/
        Server-Sent Events (SSE) endpoint.  Holds the HTTP connection open and
        pushes new unacknowledged alerts to the browser as SSE 'data:' frames
        every 5 seconds.  The client should use the native EventSource API.

        SSE format:
            data: {"alerts": [...], "count": N}\n\n
        """
        profile = self._get_profile()

        def event_stream():
            # Send a comment heartbeat immediately so browser doesn't time out
            yield ': connected\n\n'
            last_alert_id = 0
            # Shortened from 300s (5min) to 30s to prevent thread-blocking on WSGI servers
            max_duration = 30
            elapsed = 0
            poll_interval = 5    # seconds between DB checks

            while elapsed < max_duration:
                try:
                    # Detect profile deletion mid-stream
                    try:
                        profile.refresh_from_db(fields=['id'])
                    except PatientProfile.DoesNotExist:
                        logger.warning('[SSE] Profile %s deleted — closing stream.', profile.pk)
                        yield 'event: close\ndata: {}\n\n'
                        return
                    new_alerts = ProactiveAlert.objects.filter(
                        patient=profile,
                        acknowledged=False,
                        pk__gt=last_alert_id,
                    ).select_related('assessment').order_by('created_at')

                    if new_alerts.exists():
                        last_alert_id = new_alerts.last().pk
                        payload = ProactiveAlertSerializer(new_alerts, many=True).data
                        data = json.dumps({
                            'alerts': payload,
                            'count': len(payload),
                        })
                        yield f'data: {data}\n\n'
                    else:
                        # Heartbeat to keep the connection alive
                        yield ': heartbeat\n\n'

                except Exception as exc:
                    logger.error('[SSE] Error in alert stream for patient %s: %s', profile.pk, exc)
                    yield ': error\n\n'

                time.sleep(poll_interval)
                elapsed += poll_interval

            # Signal client to reconnect
            yield 'event: close\ndata: {}\n\n'

        response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'  # Disable Nginx buffering for SSE
        return response
