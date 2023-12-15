from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from django.http import HttpResponse
from django.utils.translation import gettext as _
from django.template.loader import get_template

from attendance.models import BiometricEmployees
from attendance.views.clock_in_out import clock_in, clock_out
from employee.models import EmployeeWorkInformation
from zk import ZK




# class BioThread(Thread):
#     def __init__(self, users, employees, conn, request):
#         self.users = users
#         self.employees = employees
#         self.conn = conn
#         self.request = request
#         Thread.__init__(self)

#     def run(self):
#         users = self.users
#         employees = self.employees
#         conn = self.conn
#         results = []
#         for user in users:
#             user_id = user.user_id
#             bio_id = BiometricEmployees.objects.filter(user_id=user_id).first()
#             if bio_id:
#                 employee = bio_id.employee_id
#                 employee_work_info = EmployeeWorkInformation.objects.filter(
#                     employee_id=employee
#                 ).first()
#                 # print(employee_work_info.__dict__)
#                 if employee_work_info:
#                     work_email = (
#                         employee_work_info.email if employee_work_info.email else None
#                     )
#                     phone = (
#                         employee_work_info.mobile if employee_work_info.mobile else None
#                     )
#                     job_position = (
#                         employee_work_info.job_position_id
#                         if employee_work_info.job_position_id
#                         else None
#                     )
#                     user.__dict__["work_email"] = work_email
#                     user.__dict__["phone"] = phone
#                     user.__dict__["job_position"] = job_position
#                 else:
#                     user.__dict__["work_email"] = None
#                     user.__dict__["phone"] = None
#                     user.__dict__["job_position"] = None
#                 for i in range(0, 10):
#                     template = conn.get_user_template(uid=user.uid, temp_id=i)
#                     if template:
#                         break
#                 user.__dict__["employee"] = employee
#                 user.__dict__["badge_id"] = employee.badge_id
#                 user.__dict__["finger"] = template
#                 results.append(user)
#                 # for i in range(0, 10):
#                 #     template = conn.get_user_template(uid=user.uid, temp_id=i)
#                 #     if template is not None:
#                 #         break
#         return results
