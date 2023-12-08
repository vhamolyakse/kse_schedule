from optapy import problem_fact, planning_id, planning_entity, planning_variable
from optapy import planning_solution, planning_entity_collection_property, \
                   problem_fact_collection_property, \
                   value_range_provider, planning_score
from optapy.score import HardSoftScore

@problem_fact
class StudentGroup:
    def __init__(self, id, name, students_count):
        self.id = id
        self.name = name
        self.students_count = students_count
        

    @planning_id
    def get_id(self):
        return self.id

    def __str__(self):
        return f"StudentGroup(id={self.id}, name={self.name}, students={self.students_count})"



@problem_fact
class Teacher:
    def __init__(self, name, availability=None):
        self.name = name
        self.availability = availability

    def is_available(self, timeslot):
        return self.availability.get(timeslot.id, 0) == 1

    def __str__(self):
        return f"Teacher(name={self.name})"
    

from optapy import problem_fact, planning_id
@problem_fact
class Room:
    def __init__(self, id, name, capacity):
        self.id = id
        self.name = name
        self.capacity = capacity

    @planning_id
    def get_id(self):
        return self.id

    def __str__(self):
        return f"Room(id={self.id}, name={self.name} capacity={self.capacity})"
    

@problem_fact
class Timeslot:
    def __init__(self, id, day_of_week, start_time, end_time):
        self.id = id
        self.day_of_week = day_of_week
        self.start_time = start_time
        self.end_time = end_time

    @planning_id
    def get_id(self):
        return self.id

    def __str__(self):
        return (
                f"Timeslot("
                f"id={self.id}, "
                f"day_of_week={self.day_of_week}, "
                f"start_time={self.start_time}, "
                f"end_time={self.end_time})"
        )


@planning_entity
class Lesson:
    def __init__(self, id, subject, teacher, teacher_id, is_lection, student_group, student_group_capacity, group_intersection, timeslot=None, room=None, ideal_timeslot_id=None, ideal_room_id=None, forbidden_timeslots=None, is_fixed=False):
        self.id = id
        self.subject = subject
        self.is_fixed = is_fixed
        self.teacher = teacher
        self.teacher_id = teacher_id
        self.is_lection = is_lection
        self.student_group = student_group
        self.student_group_capacity = student_group_capacity
        self.timeslot = timeslot
        self.room = room
        self.ideal_timeslot_id = ideal_timeslot_id
        self.ideal_room_id = ideal_room_id
        self.forbidden_timeslots = forbidden_timeslots if forbidden_timeslots else {}
        self.group_intersection = group_intersection



    def get_students(self):
        return self.student_group.students if self.student_group is not None else []

    @planning_id
    def get_id(self):
        return self.id

    @planning_variable(Timeslot, value_range_provider_refs=["timeslotRange"], nullable=False)
    def get_timeslot(self):
      return self.timeslot

      #return self.timeslot

    def set_timeslot(self, new_timeslot):
        self.timeslot = new_timeslot

    @planning_variable(Room, ["roomRange"])
    def get_room(self):
        return self.room

    def set_room(self, new_room):
        self.room = new_room

    def __str__(self):
        return (
            f"Lesson("
            f"id={self.id}, "
            f"timeslot={self.timeslot}, "
            f"room={self.room}, "
            f"teacher={self.teacher.name}, "
            f"subject={self.subject}, "
            f"ideal_timeslot={self.ideal_timeslot_id}, "
            f"student_group={self.student_group}"
            f")"
        )



def format_list(a_list):
    return ',\n'.join(map(str, a_list))

@planning_solution
class TimeTable:
    def __init__(self, timeslot_list, room_list, lesson_list, score=None):
        self.timeslot_list = timeslot_list
        self.room_list = room_list
        self.lesson_list = lesson_list
        self.score = score

    @problem_fact_collection_property(Timeslot)
    @value_range_provider("timeslotRange")
    def get_timeslot_list(self):
        return self.timeslot_list

    @problem_fact_collection_property(Room)
    @value_range_provider("roomRange")
    def get_room_list(self):
        return self.room_list

    @planning_entity_collection_property(Lesson)
    def get_lesson_list(self):
        return self.lesson_list

    @problem_fact_collection_property(StudentGroup)
    def get_student_group_list(self):
        covered_group_ids = []
        group_list = []
        for lesson in self.lesson_list:
            if lesson.student_group.id not in covered_group_ids:
                group_list.append(lesson.student_group)
                covered_group_ids.append(lesson.student_group.id)

        return group_list

    @planning_score(HardSoftScore)
    def get_score(self):
        return self.score

    def set_score(self, score):
        self.score = score

    def __str__(self):
        return (
            f"TimeTable("
            f"timeslot_list={format_list(self.timeslot_list)},\n"
            f"room_list={format_list(self.room_list)},\n"
            f"lesson_list={format_list(self.lesson_list)},\n"
            f"score={str(self.score.toString()) if self.score is not None else 'None'}"
            f")"
        )
