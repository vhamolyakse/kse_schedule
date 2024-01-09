from .entities import *
from optapy import config
from optapy import constraint_provider, get_class
from optapy.constraint import Joiners
from optapy.score import HardSoftScore
from loguru import logger

from jpype import JPackage

LessonClass = get_class(Lesson)
RoomClass = get_class(Room)

SOLVING_DURATION = 60


@constraint_provider
def define_constraints(constraint_factory):
    return [
        # Hard constraints
        room_conflict(constraint_factory),
        teacher_conflict(constraint_factory),
        teacher_availability_conflict(constraint_factory),
        student_group_conflict(constraint_factory),
        room_capacity_conflict(constraint_factory),
        student_conflict(constraint_factory),
        room_online_offline_conflict(constraint_factory),
        # prefer_online_lessons_on_available_days(constraint_factory),
        lecture_order_conflict(constraint_factory),
        penalize_lesson_not_in_ideal_timeslot(constraint_factory),
        penalize_lesson_not_in_ideal_room(constraint_factory),
        penalize_lesson_in_forbidden_timeslot(constraint_factory)
        # multiple_groups_same_subject_together()
        # Soft constraints are only implemented in the optapy-quickstarts code
    ]


def room_conflict(constraint_factory):
    # A room can accommodate at most one lesson at the same time.
    return constraint_factory \
        .forEach(LessonClass) \
        .filter(lambda lesson: lesson.is_online == 0) \
        .join(LessonClass,
              [
                  # ... in the same timeslot ...
                  Joiners.equal(lambda lesson: lesson.timeslot),
                  # ... in the same room ...
                  Joiners.equal(lambda lesson: lesson.room),
                  # ... and the pair is unique (different id, no reverse pairs) ...
                  Joiners.lessThan(lambda lesson: lesson.id),
                  # ... exclude the conflict for online rooms ...
                  Joiners.filtering(lambda lessonA, lessonB: not (lessonA.room.is_online or lessonB.room.is_online))
              ]) \
        .penalize("Room conflict", HardSoftScore.ONE_HARD)


def teacher_conflict(constraint_factory):
    # A teacher can teach at most one lesson at the same time.
    return constraint_factory \
        .forEach(LessonClass) \
        .join(LessonClass,
              [
                  Joiners.equal(lambda lesson: lesson.timeslot),
                  Joiners.equal(lambda lesson: lesson.teacher.name),
                  Joiners.lessThan(lambda lesson: lesson.id)
              ]) \
        .penalize("Teacher conflict", HardSoftScore.ONE_HARD)


def student_group_conflict(constraint_factory):
    # A student can attend at most one lesson at the same time.
    return constraint_factory \
        .forEach(LessonClass) \
        .join(LessonClass,
              [
                  Joiners.equal(lambda lesson: lesson.timeslot),
                  Joiners.equal(lambda lesson: lesson.student_group),
                  Joiners.lessThan(lambda lesson: lesson.id)
              ]) \
        .penalize("Student group conflict", HardSoftScore.ONE_HARD)


def multiple_groups_same_subject_together(constraint_factory):
    # If two student groups are listening to the same subject at the same time,
    # they must be in the same room.
    return constraint_factory \
        .forEach(LessonClass) \
        .join(LessonClass,
              [
                  # ... in the same timeslot ...
                  Joiners.equal(lambda lesson: lesson.timeslot),
                  # ... for the same subject ...
                  Joiners.equal(lambda lesson: lesson.subject),
                  # ... and the pair is unique (different id, no reverse pairs) ...
                  Joiners.lessThan(lambda lesson: lesson.id),
                  # ... but different student groups ...
                  Joiners.filtering(lambda lessonA, lessonB: lessonA.student_group != lessonB.student_group),
                  # ... and different rooms ...
                  Joiners.filtering(lambda lessonA, lessonB: lessonA.room != lessonB.room)
              ]) \
        .penalize("Multiple student groups for the same subject must be together", HardSoftScore.ONE_HARD)


def room_capacity_conflict(constraint_factory):
    # A room must have a capacity greater than or equal to the student group size.
    return constraint_factory \
        .forEach(LessonClass) \
        .filter(lambda lesson: lesson.room is not None and
                               lesson.room.capacity < lesson.student_group_capacity) \
        .penalize("Unique Room capacity conflict", HardSoftScore.ONE_HARD)


def teacher_availability_conflict(constraint_factory):
    # A lesson can only be scheduled in a time slot if the teacher is available.
    return constraint_factory \
        .forEach(LessonClass) \
        .filter(lambda lesson: not lesson.teacher.is_available(lesson.timeslot)) \
        .penalize("Teacher availability conflict", HardSoftScore.ONE_HARD)


def student_conflict(constraint_factory):
    # Students in intersecting groups cannot attend lessons at the same time.
    return constraint_factory \
        .forEach(LessonClass) \
        .join(LessonClass,
              [
                  Joiners.equal(lambda lesson: lesson.timeslot),
                  Joiners.lessThan(lambda lesson: lesson.id),
                  # Check if the student groups of the two lessons intersect
                  Joiners.filtering(lambda lessonA, lessonB:
                                    lessonA.group_intersection.get(lessonA.student_group.name, {}).get(
                                        lessonB.student_group.name, 0) == 1 or
                                    lessonA.group_intersection.get(lessonB.student_group.name, {}).get(
                                        lessonA.student_group.name, 0) == 1)
              ]) \
        .penalize("Student conflict", HardSoftScore.ONE_HARD)


def room_online_offline_conflict(constraint_factory):
    return constraint_factory \
        .forEach(LessonClass) \
        .filter(lambda lesson: lesson.room is not None and (
        # Penalize online lessons not in online rooms
            (lesson.is_online == 1 and lesson.room.is_online == 0) or
            # Penalize offline lessons in online rooms if the teacher doesn't need online
            (lesson.is_online == 0 and lesson.room.is_online == 1 and not lesson.teacher.need_online(
                lesson.timeslot)) or
            # Penalize assigning offline rooms when the teacher needs an online room
            (lesson.is_online == 0 and lesson.room.is_online == 0 and lesson.teacher.need_online(lesson.timeslot))
    )) \
        .penalize("Room online offline conflict", HardSoftScore.ONE_HARD)


def lecture_order_conflict(constraint_factory):
    return constraint_factory \
        .forEach(Lesson) \
        .join(Lesson,
              [
                  # Join condition: for the same subject
                  Joiners.equal(lambda lesson: lesson.subject),
                  # Ensure we're not comparing the same lesson to itself
                  Joiners.lessThan(lambda lesson: lesson.id),
                  # Ensure one is a lecture and the other is a practice
                  Joiners.filtering(lambda lesson, other_lesson:
                                    (lesson.is_lection == 1 and other_lesson.is_lection == 0) or
                                    (lesson.is_lection == 0 and other_lesson.is_lection == 1))
              ]) \
        .filter(lambda lesson, other_lesson:
                lesson.is_lection == 1 and other_lesson.is_lection == 0 and
                lesson.timeslot.id >= other_lesson.timeslot.id) \
        .penalize("LectureBeforePracticeConflict", HardSoftScore.ONE_HARD)

    # def prefer_online_lessons_on_available_days(constraint_factory):


#     # Prefer scheduling online lessons for teachers on their available online days
#     return constraint_factory \
#         .forEach(LessonClass) \
#         .filter(lambda lesson: not lesson.teacher.need_online(lesson.timeslot and
#                                 lesson.room.is_online == 0)) \
#         .penalize("Prefer online lessons on available days", HardSoftScore.ONE_HARD)


def penalize_lesson_not_in_ideal_timeslot(constraint_factory):
    # Apply a penalty if a lesson's timeslot is not the same as its ideal timeslot.
    return constraint_factory \
        .forEach(Lesson) \
        .filter(lambda lesson: lesson.is_fixed and lesson.timeslot.id != lesson.ideal_timeslot_id) \
        .penalize("Lesson not in ideal timeslot", HardSoftScore.ofHard(10))  # Increased penalty


def penalize_lesson_not_in_ideal_room(constraint_factory):
    # Apply a penalty if a lesson's room is not the same as its ideal room.
    return constraint_factory \
        .forEach(Lesson) \
        .filter(lambda lesson: lesson.is_fixed and lesson.room.id != lesson.ideal_room_id) \
        .penalize("Lesson not in ideal room", HardSoftScore.ONE_HARD)  # Increased penalty


def penalize_lesson_in_forbidden_timeslot(constraint_factory):
    print("NEW VERSION V23")

    def log_and_return(lesson):
        # if lesson.id == 2:
        #     logger.debug(f"lesson.timeslot.id {lesson.timeslot.id}; lesson.forbidden_timeslots: {lesson.forbidden_timeslots}")
        # if lesson.forbidden_timeslots.get(lesson.timeslot.id, 0) == 1:
        #     logger.debug(f"Penalizing: {lesson.id} in timeslot {lesson.timeslot.id}")
        return lesson.forbidden_timeslots.get(lesson.timeslot.id, 0) == 1

    return constraint_factory \
        .forEach(Lesson) \
        .filter(log_and_return) \
        .penalize("Lesson in forbidden timeslot", HardSoftScore.ofHard(20))


def get_solver_config(solving_duration):
    best_score_termination = config.solver.termination.TerminationConfig() \
        .withBestScoreLimit("0hard/0soft")

    time_spent_termination = config.solver.termination.TerminationConfig() \
        .withSecondsSpentLimit(solving_duration)

    ArrayList = JPackage("java").util.ArrayList
    termination_list = ArrayList()
    termination_list.add(best_score_termination)
    termination_list.add(time_spent_termination)

    composite_termination_config = config.solver.termination.TerminationConfig() \
        .withTerminationConfigList(termination_list) \
        .withTerminationCompositionStyle(config.solver.termination.TerminationCompositionStyle.OR)

    solver_config = config.solver.SolverConfig() \
        .withEntityClasses(get_class(Lesson)) \
        .withSolutionClass(get_class(TimeTable)) \
        .withConstraintProviderClass(get_class(define_constraints)) \
        .withTerminationConfig(composite_termination_config) \
        .withPhases([
            config.constructionheuristic.ConstructionHeuristicPhaseConfig(),
            config.localsearch.LocalSearchPhaseConfig()
            .withAcceptorConfig(
                config.localsearch.decider.acceptor.LocalSearchAcceptorConfig()
                .withSimulatedAnnealingStartingTemperature("0hard/0soft")
            )
        ])
    return solver_config
