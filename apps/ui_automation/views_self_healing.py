"""Self-healing stats API."""
from __future__ import annotations

from datetime import timedelta

from django.db.models import Count, Q, Sum
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import AutoFixProposal, Element, FailureDiagnosis


class SelfHealingViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def stats(self, request):
        days = int(request.query_params.get('days') or 30)
        project_id = request.query_params.get('project_id') or request.query_params.get('project')
        since = timezone.now() - timedelta(days=max(1, min(days, 365)))

        diagnoses = FailureDiagnosis.objects.filter(created_at__gte=since)
        proposals = AutoFixProposal.objects.filter(created_at__gte=since)
        elements = Element.objects.all()
        if project_id:
            diagnoses = diagnoses.filter(project_id=project_id)
            proposals = proposals.filter(diagnosis__project_id=project_id)
            elements = elements.filter(project_id=project_id)

        by_category = list(
            diagnoses.values('category').annotate(count=Count('id')).order_by('-count')
        )
        proposal_counts = {
            'proposed': proposals.filter(status='proposed').count(),
            'applied': proposals.filter(status='applied').count(),
            'rejected': proposals.filter(status='rejected').count(),
            'rolled_back': proposals.filter(status='rolled_back').count(),
        }
        verify_counts = {
            'pending': proposals.filter(verify_status='pending').count(),
            'passed': proposals.filter(verify_status='passed').count(),
            'failed': proposals.filter(verify_status='failed').count(),
            'skipped': proposals.filter(verify_status='skipped').count(),
        }
        applied = proposal_counts['applied'] or 0
        passed = verify_counts['passed'] or 0
        success_rate = round((passed / applied) * 100, 1) if applied else 0.0

        promote_count = proposals.filter(
            Q(patch_payload__type='promote_backup') | Q(title__icontains='升格')
        ).count()
        backup_hit_diagnoses = diagnoses.filter(
            evidence__context__used_backup=True
        ).count()

        heal_agg = elements.aggregate(
            total_heal_count=Sum('heal_count'),
            healed_elements=Count('id', filter=Q(heal_count__gt=0)),
        )

        return Response({
            'days': days,
            'project_id': int(project_id) if project_id else None,
            'diagnosis_total': diagnoses.count(),
            'by_category': by_category,
            'proposals': proposal_counts,
            'verification': verify_counts,
            'success_rate': success_rate,
            'promote_count': promote_count,
            'backup_hit_count': backup_hit_diagnoses,
            'rollback_count': proposal_counts['rolled_back'],
            'verify_fail_rate': round(
                (verify_counts['failed'] / applied) * 100, 1
            ) if applied else 0.0,
            'element_heals': {
                'total_heal_count': heal_agg.get('total_heal_count') or 0,
                'healed_elements': heal_agg.get('healed_elements') or 0,
            },
        })
