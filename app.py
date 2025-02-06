import streamlit as st
import pandas as pd
import numpy as np
import random  # for shuffling
from datetime import datetime, timedelta, date

# Import the CP-SAT solver from OR-Tools.
from ortools.sat.python import cp_model

# Initialize session state for schedule if not already set.
if "schedule" not in st.session_state:
    st.session_state.schedule = None
if "schedule_dates" not in st.session_state:
    st.session_state.schedule_dates = None
if "valid_names" not in st.session_state:
    st.session_state.valid_names = None

st.title("Nurse Shift Scheduling Wheel")
st.markdown("""
This app creates a 12‑week cyclical schedule for 12 nurses under these conditions:
- **Daily staffing:** 3 nurses on Day shift and 2 on Night shift (each a 12‑hour shift).
- **Weekend rule:** If a nurse works on Saturday or Sunday, they work both days.
- **Consecutive work days:** No nurse works more than 3 days in a row.
- **Rest requirement:** If a nurse works a Night shift, they cannot work a Day shift the following day.
- **Maximum rest period:** No nurse may have more than **9 consecutive off‑shift periods**.
  (Since each day has 2 shifts, 5 days off would be 10 off‑shift periods. Therefore, in every block of 5 consecutive days, a nurse must work at least once.)
- **Fair distribution:** Over 12 weeks each nurse is intended to work **35 shifts**.
""")

st.header("Schedule Settings")

# --- Option to choose the schedule start date ---
start_date = st.date_input("Select the schedule start date", value=date.today())

# ----- Nurse Information -----
st.header("Step 1. Enter Nurse Names (12 total)")
nurse_names = []
for i in range(12):
    name = st.text_input(f"Nurse #{i+1} Name", key=f"name_{i}")
    nurse_names.append(name.strip())

if st.button("Generate Schedule"):
    # Validate nurse names: require exactly 12 non-empty names.
    valid_names = [name for name in nurse_names if name != ""]
    if len(valid_names) != 12:
        st.error("Please enter a name for each of the 12 nurses.")
    else:
        st.info("Building schedule – please wait...")

        # ----- SCHEDULING MODEL PARAMETERS -----
        num_nurses = 12
        num_weeks = 12
        days_per_week = 7
        horizon = num_weeks * days_per_week  # 84 days

        # Compute the list of dates for the schedule based on the start_date.
        schedule_dates = [start_date + timedelta(days=d) for d in range(horizon)]

        # Shifts: 0 = Day, 1 = Night.
        required_shifts_per_day = {0: 3, 1: 2}  # per day

        # Create the CP-SAT model.
        model = cp_model.CpModel()

        # Create decision variables:
        # x[n, d, s] = 1 if nurse n works on day d on shift s.
        x = {}
        for n in range(num_nurses):
            for d in range(horizon):
                for s in [0, 1]:
                    x[n, d, s] = model.NewBoolVar(f"x_n{n}_d{d}_s{s}")

        # --- Constraint 1: Daily shift requirements ---
        for d in range(horizon):
            for s in [0, 1]:
                model.Add(sum(x[n, d, s] for n in range(num_nurses)) == required_shifts_per_day[s])

        # --- Constraint 2: At most one shift per nurse per day ---
        for n in range(num_nurses):
            for d in range(horizon):
                model.Add(x[n, d, 0] + x[n, d, 1] <= 1)

        # --- Constraint 3: No more than 3 consecutive work days ---
        for n in range(num_nurses):
            for d in range(horizon - 3):
                model.Add(sum(x[n, d + i, 0] + x[n, d + i, 1] for i in range(4)) <= 3)

        # --- Constraint 4: Weekend pairing (Saturday and Sunday linked) ---
        # Assuming day 0 is Monday so Saturday is index 5 and Sunday is index 6.
        for n in range(num_nurses):
            for week in range(num_weeks):
                sat = week * days_per_week + 5
                sun = week * days_per_week + 6
                sat_work = model.NewIntVar(0, 1, f"sat_n{n}_w{week}")
                sun_work = model.NewIntVar(0, 1, f"sun_n{n}_w{week}")
                model.Add(sat_work == x[n, sat, 0] + x[n, sat, 1])
                model.Add(sun_work == x[n, sun, 0] + x[n, sun, 1])
                model.Add(sat_work == sun_work)

        # --- Constraint 5: Fair distribution of shifts ---
        for n in range(num_nurses):
            model.Add(sum(x[n, d, s] for d in range(horizon) for s in [0, 1]) == 35)

        # --- Constraint 6: Rest after a Night shift ---
        for n in range(num_nurses):
            for d in range(horizon - 1):
                model.Add(x[n, d, 1] + x[n, d + 1, 0] <= 1)

        # --- Constraint 7: Maximum consecutive off-shift periods (9 off-shifts) ---
        # In every block of 5 consecutive days, each nurse must work at least one shift.
        for n in range(num_nurses):
            for d in range(horizon - 4):
                model.Add(sum(x[n, d + i, 0] + x[n, d + i, 1] for i in range(5)) >= 1)

        # --- Introduce randomness into the solution process ---
        # Instead of using a dummy or fixed search, we add an objective with random coefficients.
        # This forces the solver to choose a solution that maximizes this random objective,
        # thereby selecting randomly among the many feasible solutions.
        rand_obj = []
        for n in range(num_nurses):
            for d in range(horizon):
                for s in [0, 1]:
                    rand_obj.append(random.randint(0, 10) * x[n, d, s])
        model.Maximize(sum(rand_obj))

        # Optionally, also set a random seed for CP-SAT.
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 60.0
        solver.parameters.random_seed = random.randint(0, 1000000)

        status = solver.Solve(model)
        if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            st.success("Schedule generated successfully!")

            # Build a schedule table: rows = days, columns = nurses.
            schedule = np.empty((horizon, num_nurses), dtype=object)
            schedule[:] = ""  # initialize

            for d in range(horizon):
                for n in range(num_nurses):
                    if solver.Value(x[n, d, 0]) == 1:
                        schedule[d, n] = "D"
                    elif solver.Value(x[n, d, 1]) == 1:
                        schedule[d, n] = "N"
                    else:
                        schedule[d, n] = ""

            # --- Introduce randomness by shuffling the nurse order ---
            st.session_state.schedule = schedule
            st.session_state.valid_names = valid_names

        else:
            st.error("No feasible schedule was found. Please adjust parameters and try again.")


# --- SHIFT EXCHANGE FEATURE ---
if st.session_state.schedule is not None:
    st.header("Shift Exchange")
    st.markdown(
        "Select two cells to exchange their assignments. The exchange is allowed even if one cell is empty (an off day), so you can swap a shift for a day off."
    )

    valid_names = st.session_state.valid_names
    schedule_dates = st.session_state.schedule_dates
    schedule = st.session_state.schedule
    horizon = len(schedule_dates)

    # Create a list of string labels for days with their index included.
    day_options = [f"{i}: {schedule_dates[i].strftime('%b %d (%a)')}" for i in range(horizon)]

    st.subheader("Select Cell A")
    nurse_a = st.selectbox("Nurse A", valid_names, key="nurse_a")
    day_a_option = st.selectbox("Day A (select the day index)", day_options, key="day_a")
    day_a_index = int(day_a_option.split(":")[0])

    st.subheader("Select Cell B")
    nurse_b = st.selectbox("Nurse B", valid_names, key="nurse_b")
    day_b_option = st.selectbox("Day B (select the day index)", day_options, key="day_b")
    day_b_index = int(day_b_option.split(":")[0])

    if st.button("Exchange Shifts"):
        # Find column indices for each nurse.
        try:
            nurse_a_index = valid_names.index(nurse_a)
            nurse_b_index = valid_names.index(nurse_b)
        except ValueError:
            st.error("Nurse name not found in the list.")
        else:
            # Retrieve the current assignments.
            cell_a = schedule[day_a_index, nurse_a_index]
            cell_b = schedule[day_b_index, nurse_b_index]

            # Check if both cells are off days.
            if cell_a == "" and cell_b == "":
                st.error("Both selected cells are off days; nothing to exchange.")
            else:
                # Swap the assignments.
                schedule[day_a_index, nurse_a_index] = cell_b
                schedule[day_b_index, nurse_b_index] = cell_a

                st.success(
                    f"Exchanged {nurse_a}'s assignment on day {day_a_index} with {nurse_b}'s assignment on day {day_b_index}."
                )
                # Save the updated schedule back to session state.
                st.session_state.schedule = schedule

# --- Always display the current schedule ---
if st.session_state.schedule is not None:
    st.subheader("Current Schedule Grid")
    day_labels = [dt.strftime("%b %d (%a)") for dt in st.session_state.schedule_dates]
    df = pd.DataFrame(st.session_state.schedule, index=day_labels, columns=st.session_state.valid_names)
    st.dataframe(df.style.set_properties(**{"text-align": "center"}))
    
    st.markdown("""
    **Legend:**
    - **D:** Day shift (12 hours)
    - **N:** Night shift (12 hours)
    - **Blank:** Day off
    """)