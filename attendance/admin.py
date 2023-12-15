"""
admin.py

This page is used to register attendance models with admins site.
"""
from django.contrib import admin
from .models import (
    Attendance,
    AttendanceActivity,
    AttendanceOverTime,
    AttendanceLateComeEarlyOut,
    AttendanceValidationCondition,
    BiometricAttendance,
    BiometricDevices,
    BiometricEmployees,
)

# Register your models here.
admin.site.register(Attendance)
admin.site.register(AttendanceActivity)
admin.site.register(AttendanceOverTime)
admin.site.register(AttendanceLateComeEarlyOut)
admin.site.register(AttendanceValidationCondition)
admin.site.register(BiometricAttendance)
admin.site.register(BiometricDevices)
admin.site.register(BiometricEmployees)
