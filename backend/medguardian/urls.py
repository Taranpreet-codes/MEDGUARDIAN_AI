from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from accounts.views import RegisterView
from patients.views import PatientProfileViewSet, MedicationCabinetViewSet, AlertViewSet
from prescriptions.views import PrescriptionViewSet

# Register API Viewsets
router = DefaultRouter()
router.register(r'patients/cabinet', MedicationCabinetViewSet, basename='medication-cabinet')
router.register(r'prescriptions', PrescriptionViewSet, basename='prescription')


def health_check(request):
    return JsonResponse({
        "status": "ok",
        "service": "MedGuardian AI Core API",
        "version": "2.0.0-beta",
        "stage": "Proactive Medication Digital Twin",
        "disclaimer": (
            "MedGuardian AI is an educational clinical decision support tool and is not a "
            "substitute for professional medical advice, diagnosis, or treatment."
        )
    })


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/health/', health_check, name='health-check'),

    # Auth Endpoints
    path('api/auth/register/', RegisterView.as_view(), name='auth-register'),
    path('api/auth/token/', TokenObtainPairView.as_view(), name='auth-token-obtain'),
    path('api/auth/token/refresh/', TokenRefreshView.as_view(), name='auth-token-refresh'),

    # ── Profile Endpoint (singleton '/api/patients/profile/me/')
    path('api/patients/profile/safety-check/', PatientProfileViewSet.as_view({'get': 'safety_check'}), name='patient-safety-check'),
    path('api/patients/profile/chat-ask/', PatientProfileViewSet.as_view({'post': 'chat_ask'}), name='patient-chat-ask'),
    path('api/patients/profile/report-patient/', PatientProfileViewSet.as_view({'get': 'report_patient'}), name='patient-report-patient'),
    path('api/patients/profile/report-clinician/', PatientProfileViewSet.as_view({'get': 'report_clinician'}), name='patient-report-clinician'),
    path('api/patients/profile/', PatientProfileViewSet.as_view({'get': 'me', 'put': 'me', 'patch': 'me'}), name='patient-profile'),
    path('api/patients/profile/me/', PatientProfileViewSet.as_view({'get': 'me', 'put': 'me', 'patch': 'me'}), name='patient-profile-me'),

    # ── Stage 2: Safety History Timeline
    path('api/patients/me/safety-history/', PatientProfileViewSet.as_view({'get': 'safety_history'}), name='patient-safety-history'),

    # ── Stage 2: Proactive Alerts
    path('api/alerts/unread/', AlertViewSet.as_view({'get': 'unread'}), name='alerts-unread'),
    path('api/alerts/stream/', AlertViewSet.as_view({'get': 'stream'}), name='alerts-stream'),
    path('api/alerts/<int:pk>/acknowledge/', AlertViewSet.as_view({'post': 'acknowledge'}), name='alerts-acknowledge'),

    # Medication & Prescription Endpoints (router)
    path('api/', include(router.urls)),
]

from django.conf import settings
from django.conf.urls.static import static

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
