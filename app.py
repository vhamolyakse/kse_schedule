import pandas as pd
import numpy as np
import os
import re
from datetime import datetime
from optapy import problem_fact, planning_id
from optapy import solver_factory_create, score_manager_create

from utils.preprocessing import strip_whitespace, get_group_intersections
from utils.entities import StudentGroup, Teacher, Room, Timeslot, Lesson, TimeTable
from utils.time_utils import get_teacher_availability, get_timeslot_list
from utils.constraints import define_constraints, get_solver_config, SOLVING_DURATION
from utils.files import process_file, convert_df_to_csv
from utils.data import DataManager
from utils.schedule import ScheduleManager
from collections import defaultdict
from datetime import time
from optapy import solver_factory_create, score_manager_create
from loguru import logger
import time
# from utils.check_constraints import check_constraints

from optapy import get_class
import optapy.config
from optapy.types import Duration
from itertools import chain

import streamlit as st
from io import StringIO
import io
import zipfile

from optapy import constraint_provider, get_class
from optapy.constraint import Joiners
from optapy.score import HardSoftScore

RESULT_DATA_PATH = 'new_schedule/input'


def parse_score_explanation(explanation_text):
    constraint_pattern = re.compile(r'(-\d+\w+): constraint \((.*?)\) has (\d+) matches:', re.DOTALL)
    indicted_object_pattern = re.compile(r'(-\d+\w+): indicted object \((.*?)\) has (\d+) matches:', re.DOTALL)

    constraints_match = constraint_pattern.findall(explanation_text)
    constraint_details = []
    for constraint_score, constraint, match_count in constraints_match:
        constraints_data = {
            "Score": constraint_score,
            "Constraint": constraint.strip(),
            "Match Count": match_count
        }
        constraint_details.append(constraints_data)

    indicted_object_match = indicted_object_pattern.findall(explanation_text)
    indicted_object_details = []
    for indicted_score, indicted_object, match_count in indicted_object_match:
        indicted_object_details.append((indicted_score.strip(), indicted_object.strip(), match_count))

    return constraint_details, indicted_object_details


def display_score_explanation(constraint_details, indicted_object_details):
    st.write("Constraint Details:")
    for constraint in constraint_details:
        st.write(f"Score: {constraint['Score']} \n Constraint: {constraint['Constraint']} \n Match Count: {constraint['Match Count']}")
        # st.write(f"Constraint: {constraint['Constraint']}")
        # st.write(f"Match Count: {constraint['Match Count']}")

    st.write("Indicted Object Details:")
    for indicted_object in indicted_object_details:
        st.write(f"Score: {indicted_object[0]}")
        st.write(f"Constraint: {indicted_object[1]}")


def generate_new_schedule(selected_date, solving_duration):
    data_manager = DataManager(RESULT_DATA_PATH, solving_duration)
    problem, error_messages = data_manager.generate_optapy_problem()
    if error_messages.size > 0:
        for msg in error_messages:
            st.error(msg)
    solver_config = get_solver_config(solving_duration)
    solver_factory = solver_factory_create(solver_config)
    solver = solver_factory.buildSolver()
    st.write(f"Going to create schedule, it will take  {solving_duration} seconds")

    solution = solver.solve(problem)
    score_manager = score_manager_create(solver_factory)
    explanation = score_manager.explainScore(solution)
    explanations = str(explanation)
    constraint_details, indicted_object_details = parse_score_explanation(explanations)

    st.write(f"Final score: {str(solution.get_score())}")
    display_score_explanation(constraint_details, indicted_object_details)
    # st.write(f"Score explanation: {str(explanation)}")

    schedule_manager = ScheduleManager(optapy_solution=solution, start_date=selected_date)
    raw_schedule_df = schedule_manager.raw_schedule_df
    json_df = schedule_manager.create_json_from_df(raw_schedule_df)
    pretty_schedule_df = schedule_manager.raw_schedule_to_pretty(raw_schedule_df)
    raw_schedule_csv = convert_df_to_csv(raw_schedule_df)
    pretty_schedule_csv = convert_df_to_csv(pretty_schedule_df)

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'a', zipfile.ZIP_DEFLATED, False) as zip_file:
        zip_file.writestr('raw_schedule.csv', raw_schedule_csv)
        zip_file.writestr('pretty_schedule.csv', pretty_schedule_csv)
        zip_file.writestr('schedule_data.json', json_df)

    zip_buffer.seek(0)

    st.download_button(
        label="Download Schedules as ZIP",
        data=zip_buffer,
        file_name='schedules.zip',
        mime='application/zip'
    )


if 'raw_schedule_df' not in st.session_state:
    st.session_state['raw_schedule_df'] = pd.DataFrame()
if 'alternatives_for_selected_lesson' not in st.session_state:
    st.session_state['alternatives_for_selected_lesson'] = []
if 'alternatives_new_raw_schedule_df' not in st.session_state:
    st.session_state['alternatives_new_raw_schedule_df'] = []
# if 'download_clicked' not in st.session_state:
#     st.session_state['download_clicked'] = False
if 'clicked' not in st.session_state:
    st.session_state.clicked = False
if 'new_swapped_raw_schedule_df' not in st.session_state:
    st.session_state['new_swapped_raw_schedule_df'] = None


# def handle_download():
#     st.session_state['download_clicked'] = True

def click_button():
    st.session_state.clicked = True


def swap_lessons_in_df(lesson_1_id, lesson_2_id, df):
    lesson_1_row = df[df['lesson_id'] == lesson_1_id]
    lesson_2_row = df[df['lesson_id'] == lesson_2_id]

    columns_to_swap = ['room', 'day', 'day_of_week', 'lesson_date', 'start_time', 'num_pair', 'room_id', 'auditory_id', 'time_slot_id']

    for col in columns_to_swap:
        temp = lesson_1_row[col].values[0]
        df.loc[df['lesson_id'] == lesson_1_id, col] = lesson_2_row[col].values[0]
        df.loc[df['lesson_id'] == lesson_2_id, col] = temp

    return df


def main():
    st.title('Schedule optimisation')

    selected_date = st.date_input("Select the date for Monday")

    if selected_date.weekday() != 0:
        st.error("Please select a Monday.")
        return

    solving_duration = st.number_input("Set the duration for solving (in seconds). If the solver finds a solution faster, it will be provided earlier.", min_value=1, value=200, step=10)

    uploaded_file = st.file_uploader("Input data for schedule")
    if uploaded_file is not None:
        process_file(uploaded_file, RESULT_DATA_PATH)

    if st.button('Generate new schedule'):
        generate_new_schedule(selected_date, solving_duration)

    existing_schedule_file = st.file_uploader("Existing raw schedule")
    # print(existing_schedule_file)

    if existing_schedule_file is None:
        print("clear cache")
        st.session_state['raw_schedule_df'] = pd.DataFrame()

    if existing_schedule_file is not None:
        logger.debug('Existing schedule')
        raw_schedule_df = pd.read_csv(existing_schedule_file)

        schedule_manager = ScheduleManager(raw_schedule_df=raw_schedule_df, start_date=selected_date)


        # new_json = schedule_manager.create_json_from_df(raw_schedule_df)
        # st.download_button(
        #     label="Download json",
        #     data=new_json,
        #     file_name='new_schedule_json.json',
        #     mime='application/new_json')

        # if st.button('Clear cache'):
        #     st.session_state['raw_schedule_df'] = pd.DataFrame()

        if st.checkbox('Full availability of the Teacher'):
            ignore_teacher_availability = True
        else:
            ignore_teacher_availability = False

        # import pdb
        # print('print1')
        # print(raw_schedule_df[["teacher", "day", "day_of_week", "lesson_date", "start_time", "lesson_id", "room"]])
        selected_option = st.selectbox('Choose the lesson you would like to reschedule:',
                                       raw_schedule_df['text'].values.tolist())

        if st.button('Show me alternative time slots'):
            if 'raw_schedule_df' in st.session_state and not st.session_state['raw_schedule_df'].empty:
                st.write("Use previously updated schedule")
                raw_schedule_df = st.session_state['raw_schedule_df'].copy()
            st.session_state['alternatives_for_selected_lesson'] = []
            st.session_state['alternatives_new_raw_schedule_df'] = []

            # print('print2')
            # print(raw_schedule_df[["teacher", "day", "day_of_week", "lesson_date", "start_time", "lesson_id"]])

            lesson_id = int(re.search(r"\[([0-9]+)\]", selected_option).group(1))

            logger.debug(f'Selected lesson_id {lesson_id}')
            selected_lesson_row = raw_schedule_df[raw_schedule_df['lesson_id'] == lesson_id].iloc[0]
            forbidden_time_slots = {selected_lesson_row['time_slot_id']: 1}
            logger.debug(f'Initial forbidden time slots: {forbidden_time_slots}')
            # print('teacher:', selected_lesson_row['teacher_id'])
            if ignore_teacher_availability:
                available_teacher = [selected_lesson_row['teacher_id']]
            else:
                available_teacher = None
            data_manager = DataManager(RESULT_DATA_PATH, solving_duration,
                                       available_teacher=available_teacher,
                                       existing_schedule_df=raw_schedule_df)
            start_time = time.time()
            time_spent = 0
            idx = 0

            # print('print3')
            # print(raw_schedule_df[["teacher", "day", "day_of_week", "lesson_date", "start_time", "lesson_id"]])

            # for i in range(2):
            while time_spent < solving_duration:
                logger.debug(f'For i : {idx} forbidden time slots: {forbidden_time_slots}')
                problem, error_messages = data_manager.generate_optapy_problem(reschedule_lesson_id=lesson_id,
                                                                               forbidden_time_slots=forbidden_time_slots)
                if error_messages.size > 0:
                    for msg in error_messages:
                        st.error(msg)
                solver_config = get_solver_config(solving_duration)
                solver_factory = solver_factory_create(solver_config)
                solver = solver_factory.buildSolver()
                st.write(f"Going to create schedule, it will take  {solving_duration} seconds")

                solution = solver.solve(problem)
                elapsed_time = time.time() - start_time
                time_spent = int(elapsed_time)
                st.write(f"Time spent: {str(time_spent)}")
                st.write(f"Final score: {str(solution.get_score())}")
                if str(solution.get_score()) != '0hard/0soft':
                    logger.debug('Solution is not good')
                    st.write(f"There is no more alternative slots")
                    break
                else:
                    st.write(f"We have one more alternative slot")
                # print('print4')
                # print(raw_schedule_df[["teacher", "day", "day_of_week", "lesson_date", "start_time", "lesson_id"]])
                new_raw_schedule_df = ScheduleManager(optapy_solution=solution, start_date=selected_date).raw_schedule_df
                # print('print5')
                # print(new_raw_schedule_df[["teacher", "day", "day_of_week", "lesson_date", "start_time", "lesson_id"]])
                new_lesson_raw_schedule = new_raw_schedule_df[new_raw_schedule_df['lesson_id'] == lesson_id].iloc[0]
                forbidden_time_slots.update({new_lesson_raw_schedule['time_slot_id']: 1})
                logger.debug(f'Forbidden time slots: {forbidden_time_slots}')
                logger.debug(f"New time slot: {new_lesson_raw_schedule['time_slot_id']}")

                st.session_state['alternatives_for_selected_lesson'].append(
                    f"{new_lesson_raw_schedule['day']} {new_lesson_raw_schedule['start_time']} {new_lesson_raw_schedule['room']}"
                )
                st.session_state['alternatives_new_raw_schedule_df'].append(new_raw_schedule_df)
                logger.debug(st.session_state['alternatives_for_selected_lesson'])

                idx += 1

    print('UPDATED VERSIONS')
    if st.session_state['alternatives_for_selected_lesson']:
        selected_option = st.selectbox('Please choose alternative time slot:',
                                       st.session_state['alternatives_for_selected_lesson'])

        if st.button('Update schedule'):
            selected_index = st.session_state['alternatives_for_selected_lesson'].index(selected_option)
            new_raw_schedule_df = st.session_state['alternatives_new_raw_schedule_df'][selected_index]
            st.session_state['raw_schedule_df'] = new_raw_schedule_df.copy()
            # import pdb
            # pdb.set_trace()

            new_pretty_schedule_df = schedule_manager.raw_schedule_to_pretty(new_raw_schedule_df)
            new_json = schedule_manager.create_json_from_df(new_raw_schedule_df)
            raw_schedule_csv = convert_df_to_csv(new_raw_schedule_df)
            pretty_schedule_csv = convert_df_to_csv(new_pretty_schedule_df)

            st.write('Updated!')

            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'a', zipfile.ZIP_DEFLATED, False) as zip_file:
                zip_file.writestr('raw_schedule.csv', raw_schedule_csv)
                zip_file.writestr('pretty_schedule.csv', pretty_schedule_csv)
                zip_file.writestr('schedule_data.json', new_json)

            zip_buffer.seek(0)

            # Create a link to download the zip file
            st.download_button(
                label="Download updated schedules as ZIP",
                data=zip_buffer,
                file_name='schedules.zip',
                mime='application/zip'
            )

            # if st.session_state['download_clicked']:
            #     st.session_state['raw_schedule_df'] = pd.DataFrame()
            #     st.write('Cash cleared!')
            #     st.session_state['download_clicked'] = False

    st.button('Swap lessons', on_click=click_button)
    if st.session_state.clicked:
        selected_lesson_1 = st.selectbox('Please select the lesson you would like to swap:',
                                         raw_schedule_df['text'].values.tolist())

        selected_lesson_2 = st.selectbox('Please select the lesson you would like to swap with the lesson 1:',
                                         raw_schedule_df['text'].values.tolist())

        if st.button("Check pair and swap"):
            st.write(f"Going to swap lessons, it will take  {solving_duration} seconds")
            if 'raw_schedule_df' in st.session_state and not st.session_state['raw_schedule_df'].empty:
                st.write("Use previously updated schedule")
                raw_schedule_df = st.session_state['raw_schedule_df'].copy()
            st.session_state['new_swapped_raw_schedule_df'] = None

            lesson_id_1 = int(re.search(r"\[([0-9]+)\]", selected_lesson_1).group(1))
            lesson_id_2 = int(re.search(r"\[([0-9]+)\]", selected_lesson_2).group(1))

            swapped_schedule_df = raw_schedule_df.copy()
            swapped_schedule_df = swap_lessons_in_df(lesson_id_1, lesson_id_2, swapped_schedule_df)

            # print('print swap')
            print(swapped_schedule_df[["teacher", "day", "day_of_week", "lesson_date", "start_time", "lesson_id", "room"]])

            selected_lesson1_row = raw_schedule_df[raw_schedule_df['lesson_id'] == lesson_id_1].iloc[0]
            selected_lesson2_row = raw_schedule_df[raw_schedule_df['lesson_id'] == lesson_id_2].iloc[0]

            if ignore_teacher_availability:
                available_teacher = [selected_lesson1_row['teacher_id']]
                available_teacher += [selected_lesson2_row['teacher_id']]
            else:
                available_teacher = None

            # print('print swap2')
            # print(raw_schedule_df[["teacher", "day", "day_of_week", "lesson_date", "start_time", "lesson_id", "room"]])

            data_manager = DataManager(RESULT_DATA_PATH, solving_duration=solving_duration,
                                       available_teacher=available_teacher,
                                       existing_schedule_df=swapped_schedule_df)
            problem, error_messages = data_manager.generate_optapy_problem()

            solver_config = get_solver_config(solving_duration)
            solver_factory = solver_factory_create(solver_config)
            solver = solver_factory.buildSolver()
            score_manager = score_manager_create(solver_factory)
            solution = solver.solve(problem)
            explanation = score_manager.explainScore(solution)
            explanations = str(explanation)
            constraint_details, indicted_object_details = parse_score_explanation(explanations)
            # formatted_explanation = display_score_explanation(constraint_details, indicted_object_details)

            st.write(f"Final score: {str(solution.get_score())}")
            display_score_explanation(constraint_details, indicted_object_details)
            print(explanations)
            # st.write(f"Score explanation:\n{formatted_explanation}")

            if str(solution.get_score()) == '0hard/0soft':
                st.session_state['new_swapped_raw_schedule_df'] = swapped_schedule_df.copy()
                st.success("Lessons swapped successfully without violating constraints.")
                # print('print6: new_raw_schedule')
                # print(st.session_state['new_swapped_raw_schedule_df'][
                #           ["teacher", "day", "day_of_week", "lesson_date", "start_time", "lesson_id"]])
            else:
                st.error("Cannot swap lessons due to constraint violations.")

            # logger.debug(f'Selected lesson_id {lesson_id_1} swap with {lesson_id_2}')
            # selected_lesson_row_1 = raw_schedule_df[raw_schedule_df['lesson_id'] == lesson_id_1].iloc[0]
            # selected_lesson_row_2 = raw_schedule_df[raw_schedule_df['lesson_id'] == lesson_id_2].iloc[0]
            #
            # if not check_constraints(selected_lesson_row_1, selected_lesson_row_2, raw_schedule_df):
            #     st.error("Cannot swap lessons due to constraint violations.")
            # else:
            #     # Perform the swap
            #     raw_schedule_df = perform_lesson_swap(lesson_1, lesson_2, raw_schedule_df)

            # if ignore_teacher_availability:
            #     available_teacher = [selected_lesson_row_1['teacher_id']]
            #     available_teacher += [selected_lesson_row_2['teacher_id']]
            #
            # else:
            #     available_teacher = None
            # data_manager = DataManager(RESULT_DATA_PATH, solving_duration,
            #                            # available_teacher=available_teacher,
            #                            existing_schedule_df=raw_schedule_df)
            # start_time = time.time()
            # time_spent = 0
            # idx = 0

            # print('print6: raw_schedule')
            # print(raw_schedule_df[["teacher", "day", "day_of_week", "lesson_date", "start_time", "lesson_id"]])

    if st.session_state['new_swapped_raw_schedule_df'] is not None:
        if st.button('Update swapped schedule'):
            new_swapped_raw_schedule_df = st.session_state['new_swapped_raw_schedule_df'].copy()
            st.session_state['raw_schedule_df'] = new_swapped_raw_schedule_df.copy()
            # import pdb
            # pdb.set_trace()

            new_pretty_schedule_df = schedule_manager.raw_schedule_to_pretty(new_swapped_raw_schedule_df)
            new_json = schedule_manager.create_json_from_df(new_swapped_raw_schedule_df)
            raw_schedule_csv = convert_df_to_csv(new_swapped_raw_schedule_df)
            pretty_schedule_csv = convert_df_to_csv(new_pretty_schedule_df)

            st.write('Updated!')

            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'a', zipfile.ZIP_DEFLATED, False) as zip_file:
                zip_file.writestr('raw_schedule.csv', raw_schedule_csv)
                zip_file.writestr('pretty_schedule.csv', pretty_schedule_csv)
                zip_file.writestr('schedule_data.json', new_json)

            zip_buffer.seek(0)

            # Create a link to download the zip file
            st.download_button(
                label="Download updated schedules as ZIP",
                data=zip_buffer,
                file_name='schedules.zip',
                mime='application/zip'
            )

if __name__ == "__main__":
    main()
