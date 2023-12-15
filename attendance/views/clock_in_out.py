"""
clock_in_out.py

This module is used register endpoints to the check-in check-out functionalities
"""
from datetime import date, datetime, timedelta
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from apscheduler.schedulers.background import BackgroundScheduler
from django.utils.translation import gettext_lazy as _
from base.models import EmployeeShiftDay
from employee.models import Employee
from horilla.decorators import login_required
from attendance.models import (
    Attendance,
    AttendanceActivity,
    AttendanceLateComeEarlyOut,
    AttendanceValidationCondition,
    BiometricDevices,
    BiometricEmployees,
)


def str_time_seconds(time):
    """
    this method is used reconvert time in H:M formate string back to seconds and return it
    args:
        time : time in H:M format
    """

    ftr = [3600, 60, 1]
    return sum(a * b for a, b in zip(ftr, map(int, time.split(":"))))


def activity_datetime(attendance_activity):
    """
    This method is used to convert clock-in and clock-out of activity as datetime object
    args:
        attendance_activity : attendance activity instance
    """

    # in
    in_year = attendance_activity.clock_in_date.year
    in_month = attendance_activity.clock_in_date.month
    in_day = attendance_activity.clock_in_date.day
    in_hour = attendance_activity.clock_in.hour
    in_minute = attendance_activity.clock_in.minute
    # out
    out_year = attendance_activity.clock_out_date.year
    out_month = attendance_activity.clock_out_date.month
    out_day = attendance_activity.clock_out_date.day
    out_hour = attendance_activity.clock_out.hour
    out_minute = attendance_activity.clock_out.minute
    return datetime(in_year, in_month, in_day, in_hour, in_minute), datetime(
        out_year, out_month, out_day, out_hour, out_minute
    )


def attendance_validate(attendance):
    """
    This method is is used to check condition for at work in AttendanceValidationCondition
    model instance it return true if at work is smaller than condition
    args:
        attendance : attendance object
    """

    conditions = AttendanceValidationCondition.objects.all()
    # Set the default condition for 'at work' to 9:00 AM
    condition_for_at_work = str_time_seconds("09:00")
    if conditions.exists():
        condition_for_at_work = str_time_seconds(conditions[0].validation_at_work)
    at_work = str_time_seconds(attendance.attendance_worked_hour)
    return condition_for_at_work >= at_work


def employee_exists(request):
    """
    This method return the employee instance and work info if not exists return None instead
    """
    employee, employee_work_info = None, None
    try:
        employee = request.user.employee_get
        employee_work_info = employee.employee_work_info
    finally:
        return (employee, employee_work_info)


def format_time(seconds):
    """
    this method is used to formate seconds to H:M and return it
    args:
        seconds : seconds
    """

    hour = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = int((seconds % 3600) % 60)
    return f"{hour:02d}:{minutes:02d}"


def overtime_calculation(attendance):
    """
    This method is used to calculate overtime of the attendance, it will
    return difference between attendance worked hour and minimum hour if
    and only worked hour greater than minimum hour, else return 00:00
    args:
        attendance : attendance instance
    """

    minimum_hour = attendance.minimum_hour
    at_work = attendance.attendance_worked_hour
    at_work_sec = str_time_seconds(at_work)
    minimum_hour_sec = str_time_seconds(minimum_hour)
    if at_work_sec > minimum_hour_sec:
        return format_time((at_work_sec - minimum_hour_sec))
    return "00:00"


def shift_schedule_today(day, shift):
    """
    This function is used to find shift schedules for the day,
    it will returns min hour,start time seconds  end time seconds
    args:
        shift   : shift instance
        day     : shift day object
    """
    schedule_today = day.day_schedule.filter(shift_id=shift)
    start_time_sec, end_time_sec, minimum_hour = 0, 0, "00:00"
    if schedule_today.exists():
        schedule_today = schedule_today[0]
        minimum_hour = schedule_today.minimum_working_hour
        start_time_sec = str_time_seconds(schedule_today.start_time.strftime("%H:%M"))
        end_time_sec = str_time_seconds(schedule_today.end_time.strftime("%H:%M"))
    return (minimum_hour, start_time_sec, end_time_sec)


def late_come_create(attendance):
    """
    used to create late come report
    args:
        attendance : attendance object
    """

    late_come_obj = AttendanceLateComeEarlyOut()
    late_come_obj.type = "late_come"
    late_come_obj.attendance_id = attendance
    late_come_obj.employee_id = attendance.employee_id
    late_come_obj.save()
    return late_come_obj


def late_come(attendance, start_time, end_time):
    """
    this method is used to mark the late check-in  attendance after the shift starts
    args:
        attendance : attendance obj
        start_time : attendance day shift start time
        end_time : attendance day shift end time

    """

    now_sec = str_time_seconds(datetime.now().strftime("%H:%M"))
    mid_day_sec = str_time_seconds("12:00")
    if start_time > end_time and start_time != end_time:
        # night shift
        if now_sec < mid_day_sec:
            # Here  attendance or attendance activity for new day night shift
            late_come_create(attendance)
        elif now_sec > start_time:
            # Here  attendance or attendance activity for previous day night shift
            late_come_create(attendance)
    elif start_time < now_sec:
        late_come_create(attendance)
    return True


def clock_in_attendance_and_activity(
    employee,
    date_today,
    attendance_date,
    day,
    now,
    shift,
    minimum_hour,
    start_time,
    end_time,
):
    """
    This method is used to create attendance activity or attendance when an employee clocks-in
    args:
        employee        : employee instance
        date_today      : date
        attendance_date : the date that attendance for
        day             : shift day
        now             : current time
        shift           : shift object
        minimum_hour    : minimum hour in shift schedule
        start_time      : start time in shift schedule
        end_time        : end time in shift schedule
    """

    # attendance activity create
    AttendanceActivity(
        employee_id=employee,
        attendance_date=attendance_date,
        clock_in_date=date_today,
        shift_day=day,
        clock_in=now,
    ).save()

    # create attendance if not exist
    attendance = Attendance.objects.filter(
        employee_id=employee, attendance_date=attendance_date
    )
    if not attendance.exists():
        attendance = Attendance()
        attendance.employee_id = employee
        attendance.shift_id = shift
        attendance.work_type_id = attendance.employee_id.employee_work_info.work_type_id
        attendance.attendance_date = attendance_date
        attendance.attendance_day = day
        attendance.attendance_clock_in = now
        attendance.attendance_clock_in_date = date_today
        attendance.minimum_hour = minimum_hour
        attendance.save()
        # check here late come or not
        late_come(attendance=attendance, start_time=start_time, end_time=end_time)
    else:
        attendance = attendance[0]
        attendance.attendance_clock_out = None
        attendance.attendance_clock_out_date = None
        attendance.save()
        # delete if the attendance marked the early out
        early_out_instance = attendance.late_come_early_out.filter(type="early_out")
        if early_out_instance.exists():
            early_out_instance[0].delete()
    return attendance


@login_required
def clock_in(request):
    """
    This method is used to mark the attendance once per a day and multiple attendance activities.
    """
    employee, work_info = employee_exists(request)
    if employee and work_info is not None:
        shift = work_info.shift_id
        date_today = date.today()
        if request.__dict__.get("date"):
            date_today = request.date
        attendance_date = date_today
        day = date_today.strftime("%A").lower()
        day = EmployeeShiftDay.objects.get(day=day)
        now = datetime.now().strftime("%H:%M")
        if request.__dict__.get("time"):
            now = request.time.strftime("%H:%M")
        now_sec = str_time_seconds(now)
        mid_day_sec = str_time_seconds("12:00")
        minimum_hour, start_time_sec, end_time_sec = shift_schedule_today(
            day=day, shift=shift
        )
        if start_time_sec > end_time_sec:
            # night shift
            # ------------------
            # Night shift in Horilla consider a 24 hours from noon to next day noon,
            # the shift day taken today if the attendance clocked in after 12 O clock.

            if mid_day_sec > now_sec:
                # Here you need to create attendance for yesterday

                date_yesterday = date_today - timedelta(days=1)
                day_yesterday = date_yesterday.strftime("%A").lower()
                day_yesterday = EmployeeShiftDay.objects.get(day=day_yesterday)
                minimum_hour, start_time_sec, end_time_sec = shift_schedule_today(
                    day=day_yesterday, shift=shift
                )
                attendance_date = date_yesterday
                day = day_yesterday
        clock_in_attendance_and_activity(
            employee=employee,
            date_today=date_today,
            attendance_date=attendance_date,
            day=day,
            now=now,
            shift=shift,
            minimum_hour=minimum_hour,
            start_time=start_time_sec,
            end_time=end_time_sec,
        )
        return HttpResponse(
            """
              <button class="oh-btn oh-btn--warning-outline "
              hx-get="/attendance/clock-out"
                  hx-target='#attendance-activity-container'
                  hx-swap='innerHTML'><ion-icon class="oh-navbar__clock-icon mr-2
                  text-warning"
                    name="exit-outline"></ion-icon>
               <span class="hr-check-in-out-text">{check_out}</span>
              </button>
            """.format(
                check_out=_("Check-Out")
            )
        )
    return HttpResponse(
        _(
            "You Don't have work information filled or your employee detail neither entered "
        )
    )


def clock_out_attendance_and_activity(employee, date_today, now):
    """
    Clock out the attendance and activity
    args:
        employee    : employee instance
        date_today  : today date
        now         : now
    """

    attendance_activities = AttendanceActivity.objects.filter(
        employee_id=employee
    ).order_by("attendance_date", "id")
    if attendance_activities.exists():
        attendance_activity = attendance_activities.last()
        attendance_activity.clock_out = now
        attendance_activity.clock_out_date = date_today
        attendance_activity.save()
    attendance_activities = attendance_activities.filter(~Q(clock_out=None)).filter(
        attendance_date=attendance_activity.attendance_date
    )
    # Here calculate the total durations between the attendance activities

    duration = 0
    for attendance_activity in attendance_activities:
        in_datetime, out_datetime = activity_datetime(attendance_activity)
        difference = out_datetime - in_datetime
        days_second = difference.days * 24 * 3600
        seconds = difference.seconds
        total_seconds = days_second + seconds
        duration = duration + total_seconds
    duration = format_time(duration)
    # update clock out of attendance
    attendance = Attendance.objects.filter(employee_id=employee).order_by(
        "-attendance_date", "-id"
    )[0]
    attendance.attendance_clock_out = now
    attendance.attendance_clock_out_date = date_today
    attendance.attendance_worked_hour = duration
    attendance.save()
    # Overtime calculation
    attendance.attendance_overtime = overtime_calculation(attendance)

    # Validate the attendance as per the condition
    attendance.attendance_validated = attendance_validate(attendance)
    attendance.save()

    return


def early_out_create(attendance):
    """
    Used to create early out report
    args:
        attendance : attendance obj
    """

    late_come_obj = AttendanceLateComeEarlyOut()
    late_come_obj.type = "early_out"
    late_come_obj.attendance_id = attendance
    late_come_obj.employee_id = attendance.employee_id
    late_come_obj.save()
    return late_come_obj


def early_out(attendance, start_time, end_time):
    """
    This method is used to mark the early check-out attendance before the shift ends
    args:
        attendance : attendance obj
        start_time : attendance day shift start time
        start_end : attendance day shift end time
    """

    now_sec = str_time_seconds(datetime.now().strftime("%H:%M"))
    mid_day_sec = str_time_seconds("12:00")
    if start_time > end_time:
        # Early out condition for night shift
        if now_sec < mid_day_sec:
            if now_sec < end_time:
                # Early out condition for general shift
                early_out_create(attendance)
        else:
            early_out_create(attendance)
        return
    if end_time > now_sec:
        early_out_create(attendance)
    return


@login_required
def clock_out(request):
    """
    This method is used to set the out date and time for attendance and attendance activity
    """
    employee, work_info = employee_exists(request)
    shift = work_info.shift_id
    date_today = date.today()
    if request.__dict__.get("date"):
        date_today = request.date
    day = date_today.strftime("%A").lower()
    day = EmployeeShiftDay.objects.get(day=day)
    attendance = (
        Attendance.objects.filter(employee_id=employee)
        .order_by("id", "attendance_date")
        .last()
    )
    if attendance is not None:
        day = attendance.attendance_day
    now = datetime.now().strftime("%H:%M")
    if request.__dict__.get("time"):
        now = request.time.strftime("%H:%M")
    minimum_hour, start_time_sec, end_time_sec = shift_schedule_today(
        day=day, shift=shift
    )
    early_out_instance = attendance.late_come_early_out.filter(type="early_out")
    if not early_out_instance.exists():
        early_out(
            attendance=attendance, start_time=start_time_sec, end_time=end_time_sec
        )

    clock_out_attendance_and_activity(employee=employee, date_today=date_today, now=now)
    return HttpResponse(
        """
              <button class="oh-btn oh-btn--success-outline " 
              hx-get="/attendance/clock-in" 
              hx-target='#attendance-activity-container' 
              hx-swap='innerHTML'>
              <ion-icon class="oh-navbar__clock-icon mr-2 text-success" 
              name="enter-outline"></ion-icon>
               <span class="hr-check-in-out-text">{check_in}</span>
              </button>
            """.format(
            check_in=_("Check-In")
        )
    )


from zk import ZK


def biometric_set_time(conn):
    # update new time to machine
    zk_time = conn.get_time()
    new_time = datetime.today()
    conn.set_time(new_time)


from threading import Thread


class Request:
    def __init__(
        self,
        user,
        date,
        time,
    ) -> None:
        self.user = user
        self.path = "/"
        self.session = {"title": None}
        self.date = date
        self.time = time


class BioAttendance(Thread):
    def __init__(self, machine_ip, port_no):
        self.machine_ip = machine_ip
        self.port_no = port_no
        zk = ZK(
            machine_ip,
            port=port_no,
            timeout=5,
            password=0,
            force_udp=False,
            ommit_ping=False,
        )
        conn = zk.connect()
        self.conn = conn
        Thread.__init__(self)

    def run(self):
        try:
            device = BiometricDevices.objects.filter(
                machine_ip=self.machine_ip, port=self.port_no
            ).first()
            if device.is_live:
                attendances = self.conn.live_capture()
                for attendance in attendances:
                    if attendance:
                        print(
                            "---------------------------------------------------------------------"
                        )
                        print(attendance.__dict__)
                        user_id = attendance.user_id
                        uid = attendance.uid
                        punch_code = attendance.punch
                        date_time = attendance.timestamp
                        date = date_time.date()
                        time = date_time.time()
                        if device:
                            device.last_fetch_date = date
                            device.last_fetch_time = time
                            device.save()
                        bio_id = BiometricEmployees.objects.filter(
                            user_id=user_id
                        ).first()
                        if bio_id:
                            if punch_code in {0, 3, 4}:
                                try:
                                    clock_in(
                                        Request(
                                            user=bio_id.employee_id.employee_user_id,
                                            date=date,
                                            time=time,
                                        )
                                    )
                                except Exception as e:
                                    print(f"Got an error in clock_in {e}")
                                    continue
                            else:
                                try:
                                    clock_out(
                                        Request(
                                            user=bio_id.employee_id.employee_user_id,
                                            date=date,
                                            time=time,
                                        )
                                    )
                                except Exception as e:
                                    print(f"Got an error in clock_out {e}")
                                    continue
                    else:
                        continue
        except ConnectionResetError as e:
            BioAttendance(self.machine_ip, self.port_no).start()


def biometric_device_live(request):
    is_live = request.GET.get("is_live")
    device_id = request.GET.get("deviceId")
    device = BiometricDevices.objects.get(id=device_id)
    is_live = True if is_live == "true" else False
    if is_live:
        title = _("Connection unsuccessful")
        text = _(
            "Please double-check the accuracy of the provided IP Address and Port Number for correctness"
        )
        port_no = device.port
        machine_ip = device.machine_ip
        conn = None
        # create ZK instance
        zk = ZK(
            machine_ip,
            port=port_no,
            timeout=5,
            password=0,
            force_udp=False,
            ommit_ping=False,
        )
        try:
            conn = zk.connect()
            instance = BioAttendance(machine_ip, port_no)
            instance.start()
            conn.test_voice(index=14)
            if conn:
                device.is_live = True
                device.is_scheduler = False
                device.save()
            text = _("The live capture mode has been activated successfully.")
            script = """<script>
                    Swal.fire({
                      text: "The live capture mode has been activated successfully.",
                      icon: "success",
                      showConfirmButton: false,
                      timer: 1500,
                      timerProgressBar: true, // Show a progress bar as the timer counts down
                      didClose: () => {
                        location.reload(); // Reload the page after the SweetAlert is closed
                        },
                    });
                    </script>
                """
        except Exception as e:
            device.is_live = False
            device.save()
            print(f"An error comes in biometric_device_live {e}")
            script = """
           <script>
                Swal.fire({
                  title : "Connection unsuccessful",
                  text: "Please double-check the accuracy of the provided IP Address and Port Number for correctness",
                  icon: "warning",
                  showConfirmButton: false,
                  timer: 3000, // Set the timer to 3000 milliseconds (3 seconds)
                  timerProgressBar: true, // Show a progress bar as the timer counts down
                  didClose: () => {
                    location.reload(); // Reload the page after the SweetAlert is closed
                    },
                });
            </script>
            """
        finally:
            if conn:
                conn.disconnect()
    else:
        device.is_live = False
        device.save()
        text = _("The live capture mode has been deactivated successfully.")
        script = """
           <script>
                Swal.fire({
                  text: "The live capture mode has been deactivated successfully.",
                  icon: "warning",
                  showConfirmButton: false,
                  timer: 3000, // Set the timer to 3000 milliseconds (3 seconds)
                  timerProgressBar: true, // Show a progress bar as the timer counts down
                  didClose: () => {
                    location.reload(); // Reload the page after the SweetAlert is closed
                    },
                });
            </script>
            """
    return JsonResponse({"script": script})


def biometric_device_attendance(device_id):
    device = BiometricDevices.objects.get(id=device_id)
    port_no = device.port
    machine_ip = device.machine_ip
    conn = None
    zk = ZK(
        machine_ip,
        port=port_no,
        timeout=5,
        password=0,
        force_udp=False,
        ommit_ping=False,
    )
    try:
        conn = zk.connect()
        conn.enable_device()
        attendances = conn.get_attendance()
        attendances = conn.get_attendance()
        last_attendance_datetime = attendances[-1].timestamp
        if device.last_fetch_date and device.last_fetch_time:
            filtered_attendances = [
                attendance
                for attendance in attendances
                if attendance.timestamp.date() >= device.last_fetch_date
                and attendance.timestamp.time() > device.last_fetch_time
            ]
        else:
            filtered_attendances = attendances
        device.last_fetch_date = last_attendance_datetime.date()
        device.last_fetch_time = last_attendance_datetime.time()
        device.save()
        for attendance in filtered_attendances:
            user_id = attendance.user_id
            punch_code = attendance.punch
            date_time = attendance.timestamp
            date = date_time.date()
            time = date_time.time()
            bio_id = BiometricEmployees.objects.filter(user_id=user_id).first()
            if bio_id:
                if punch_code in {0, 3, 4}:
                    try:
                        clock_in(
                            Request(
                                user=bio_id.employee_id.employee_user_id,
                                date=date,
                                time=time,
                            )
                        )
                    except:
                        pass
                else:
                    try:
                        clock_out(
                            Request(
                                user=bio_id.employee_id.employee_user_id,
                                date=date,
                                time=time,
                            )
                        )
                    except:
                        pass
    except Exception as e:
        print("Process terminate : {}".format(e))
    finally:
        if conn:
            conn.disconnect()

try:
    devices = BiometricDevices.objects.all().update(is_live=False)
    for device in BiometricDevices.objects.filter(is_scheduler=True):
        if device:
            if str_time_seconds(device.scheduler_duration) > 0:
                scheduler = BackgroundScheduler()
                scheduler.add_job(
                    lambda: biometric_device_attendance(device.id),
                    "interval",
                    seconds=str_time_seconds(device.scheduler_duration),
                )
                scheduler.start()
except:
    pass
