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

    st.write(f"Final score: {str(solution.get_score())}")
    st.write(f"Score explanation: {str(explanation)}")

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
if 'download_clicked' not in st.session_state:
    st.session_state['download_clicked'] = False

def handle_download():
    st.session_state['download_clicked'] = True

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
    print(existing_schedule_file)

    if existing_schedule_file is not None:
        logger.debug('Existing schedule')
        raw_schedule_df = pd.read_csv(existing_schedule_file)

        schedule_manager = ScheduleManager(raw_schedule_df=raw_schedule_df, start_date=selected_date)
        # import pdb

        selected_option = st.selectbox('Choose the lection you would like to reschedule:',
                                       raw_schedule_df['text'].values.tolist())

        if st.button('Show me alternative time slots'):
            if 'raw_schedule_df' in st.session_state and not st.session_state['raw_schedule_df'].empty:
                st.write("Use previously updated schedule")
                raw_schedule_df = st.session_state['raw_schedule_df']
            st.session_state['alternatives_for_selected_lesson'] = []
            st.session_state['alternatives_new_raw_schedule_df'] = []


            lesson_id = int(re.search(r"\[([0-9]+)\]", selected_option).group(1))

            logger.debug(f'Selected lesson_id {lesson_id}')
            selected_lesson_row = raw_schedule_df[raw_schedule_df['lesson_id'] == lesson_id].iloc[0]
            forbidden_time_slots = {selected_lesson_row['time_slot_id']: 1}
            logger.debug(f'Initial forbidden time slots: {forbidden_time_slots}')
            data_manager = DataManager(RESULT_DATA_PATH, solving_duration, existing_schedule_df=raw_schedule_df)

            start_time = time.time()  # Start timer
            time_spent = 0
            idx = 0

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
                new_raw_schedule_df = ScheduleManager(optapy_solution=solution, start_date=selected_date).raw_schedule_df
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
                mime='application/zip',
                on_click=handle_download
            )

            if st.session_state['download_clicked']:
                st.session_state['raw_schedule_df'] = []
                st.write('Cash cleared!')
                st.session_state['download_clicked'] = False


if __name__ == "__main__":
    main()
