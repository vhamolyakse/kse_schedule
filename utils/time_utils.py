from .entities import Timeslot
from datetime import datetime
from datetime import time

def get_timeslot_list():
  time_slot_per_day = [
      (time(hour=8, minute=30), time(hour=9, minute=50)),
      (time(hour=10, minute=0), time(hour=11, minute=20)),
      (time(hour=11, minute=30), time(hour=12, minute=50)),
      (time(hour=13, minute=30), time(hour=14, minute=50)),
      (time(hour=15, minute=0), time(hour=16, minute=20)),
      (time(hour=16, minute=30), time(hour=17, minute=50)),
  ]
  c = 0
  timeslot_list = []

  for day in ['MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY']:
    for t in time_slot_per_day:
      timeslot_list.append(Timeslot(c, day, t[0], t[1]))
      c += 1
  return timeslot_list


def get_time_from_string(time_string):
    return datetime.strptime(time_string, "%H:%M").time()

def get_time_slots(start_time, end_time, timeslot_list, day):
    start_datetime = datetime.combine(datetime.today(), start_time)
    end_datetime = datetime.combine(datetime.today(), end_time)
    result = []

    for timeslot in timeslot_list[day.upper()]:
        if timeslot.start_time >= start_datetime.time() and timeslot.end_time <= end_datetime.time():
            result.append(timeslot)

    return result


def try_to_convert_to_int(val):
    try:
        return int(val)
    except:
        return val
    
def get_teacher_availability(df, timeslot_dict):
    availability = {}
    days_of_week = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday']

    for index, row in df.iterrows():
        teacher_name = row['name']
        teacher_availability = {}

        for day in days_of_week:
            day_availability = {timeslot.id: 0 for timeslot in timeslot_dict[day.upper()]}
            availability_data = try_to_convert_to_int(row[day])

            if availability_data == 1:
                day_availability = {timeslot.id: 1 for timeslot in timeslot_dict[day.upper()]}
            elif availability_data != 0:
                for time_range in str(availability_data).split(","):
                    time_range = time_range.replace(' ', '')
                    start_time, end_time = map(get_time_from_string, time_range.split('-'))
                    for timeslot in get_time_slots(start_time, end_time, timeslot_dict, day.upper()):
                        day_availability[timeslot.id] = 1

            teacher_availability[day] = day_availability

        availability[teacher_name] = teacher_availability

    def foo(v):
        r = {}
        for k_1,v_1 in v.items():
            for k_2,v_2 in v_1.items():
                r[k_2] = v_2
        return r
    availability = {k: foo(v) for k, v in availability.items()}

    return availability
