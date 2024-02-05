"""
models.py

This module is used to register models for onboarding app

"""
from datetime import datetime
import threading
import time
from typing import Any
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _
from horilla_audit.models import HorillaAuditInfo, HorillaAuditLog
from recruitment.models import Recruitment, Candidate
from employee.models import Employee
from base.horilla_company_manager import HorillaCompanyManager
from django.contrib.auth.models import User


class OnboardingStage(models.Model):
    """
    OnboardingStage models
    """

    stage_title = models.CharField(max_length=200)
    recruitment_id = models.ForeignKey(
        Recruitment,
        verbose_name=_("Recruitment"),
        null=True,
        related_name="onboarding_stage",
        on_delete=models.CASCADE,
    )
    employee_id = models.ManyToManyField(Employee)
    sequence = models.IntegerField(null=True)
    is_final_stage = models.BooleanField(default=False)
    objects = HorillaCompanyManager("recruitment_id__company_id")

    def __str__(self):
        return f"{self.stage_title}"

    class Meta:
        """
        Meta class for additional options
        """

        ordering = ["sequence"]


@receiver(post_save, sender=Recruitment)
def create_initial_stage(sender, instance, created, **kwargs):
    """
    This is post save method, used to create initial stage for the recruitment
    """
    if created or not instance.onboarding_stage.first():
        initial_stage = OnboardingStage()
        initial_stage.sequence = 0
        initial_stage.stage_title = "Initial"
        initial_stage.save()
        initial_stage.recruitment_id.set([instance])


class OnboardingTask(models.Model):
    """
    OnboardingTask models
    """

    task_title = models.CharField(max_length=200)
    # recruitment_id = models.ManyToManyField(Recruitment, related_name="onboarding_task")
    stage_id = models.ForeignKey(
        OnboardingStage,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="onboarding_task",
    )
    candidates = models.ManyToManyField(
        Candidate,
        blank=True,
        related_name="cand_onboarding_task",
    )
    employee_id = models.ManyToManyField(Employee, related_name="onboarding_task")

    objects = HorillaCompanyManager("recruitment_id__company_id")

    def __str__(self):
        return f"{self.task_title}"


class CandidateStage(models.Model):
    """
    CandidateStage model
    """

    candidate_id = models.OneToOneField(
        Candidate, on_delete=models.PROTECT, related_name="onboarding_stage"
    )
    onboarding_stage_id = models.ForeignKey(
        OnboardingStage, on_delete=models.PROTECT, related_name="candidate"
    )
    onboarding_end_date = models.DateField(blank=True, null=True)
    sequence = models.IntegerField(null=True, default=0)
    objects = HorillaCompanyManager("candidate_id__recruitment_id__company_id")

    def __str__(self):
        return f"{self.candidate_id}  |  {self.onboarding_stage_id}"

    def save(self, *args, **kwargs):
        if self.onboarding_stage_id.is_final_stage:
            self.onboarding_end_date = datetime.today()
        super(CandidateStage, self).save(*args, **kwargs)

    def task_completion_ratio(self):
        # function that used for getting the numbers between task completed v/s tasks assigned
        cans_tasks = CandidateTask.objects.filter(
            candidate_id=self.candidate_id, stage_id=self.onboarding_stage_id
        )
        completed_tasks = cans_tasks.filter(status="done")
        return f"{completed_tasks.count()}/{cans_tasks.count()}"

    class Meta:
        """
        Meta class for additional options
        """

        verbose_name = _("Candidate Onboarding stage")
        ordering = ["sequence"]


class CandidateTask(models.Model):
    """
    CandidateTask model
    """

    choice = (
        ("todo", _("Todo")),
        ("scheduled", _("Scheduled")),
        ("ongoing", _("Ongoing")),
        ("stuck", _("Stuck")),
        ("done", _("Done")),
    )
    candidate_id = models.ForeignKey(
        Candidate, on_delete=models.PROTECT, related_name="candidate_task"
    )
    # managers = models.ManyToManyField(Employee)
    stage_id = models.ForeignKey(
        OnboardingStage,
        null=True,
        on_delete=models.PROTECT,
        related_name="candidate_task",
    )
    status = models.CharField(
        max_length=50, choices=choice, blank=True, null=True, default="todo"
    )
    onboarding_task_id = models.ForeignKey(OnboardingTask, on_delete=models.PROTECT)
    objects = HorillaCompanyManager("candidate_id__recruitment_id__company_id")
    history = HorillaAuditLog(
        related_name="history_set",
        bases=[
            HorillaAuditInfo,
        ],
    )

    def __str__(self):
        return f"{self.candidate_id}|{self.onboarding_task_id}"

    class Meta:
        """
        Meta class to add some additional options
        """

        verbose_name = _("Candidate onboarding task")
        # unique_together = ("candidate_id", "onboarding_task_id")


class OnboardingPortal(models.Model):
    """
    OnboardingPortal model
    """

    candidate_id = models.OneToOneField(
        Candidate, on_delete=models.PROTECT, related_name="onboarding_portal"
    )
    token = models.CharField(max_length=200)
    used = models.BooleanField(default=False)
    count = models.IntegerField(default=0)
    objects = HorillaCompanyManager("candidate_id__recruitment_id__company_id")

    def __str__(self):
        return f"{self.candidate_id} | {self.token}"


class OnboardingStageThread(threading.Thread):
    def run(self):
        time.sleep(2)
        cand = CandidateStage.objects.all()
        for c in cand:
            recruitment = c.candidate_id.recruitment_id
            stage = c.onboarding_stage_id
            if stage.recruitment_id is None:
                stage.recruitment_id = recruitment
                stage.save()
            cand_task = CandidateTask.objects.filter(candidate_id=c.candidate_id)
            for c_task in cand_task:
                if c_task.stage_id is None:
                    c_task.stage_id = stage
                    c_task.save()

                if c_task.onboarding_task_id.stage_id is None:
                    onboarding_task = c_task.onboarding_task_id
                    onboarding_task.stage_id = stage
                    onboarding_task.save

        cand_task = CandidateTask.objects.all()
        for c_task in cand_task:
            cand = c_task.candidate_id
            onboarding_task = c_task.onboarding_task_id
            if cand not in onboarding_task.candidates.all():
                onboarding_task.candidates.add(cand)
        for c_task in CandidateTask.objects.all():
            if c_task.stage_id != None and c_task.onboarding_task_id.stage_id == None:
                ob_task = c_task.onboarding_task_id
                ob_task.stage_id = c_task.stage_id
                ob_task.save()
            if c_task.stage_id == None and c_task.onboarding_task_id.stage_id != None:
                c_task.stage_id = c_task.onboarding_task_id.stage_id
                c_task.save()


try:
    OnboardingStageThread().start()
except:
    pass
