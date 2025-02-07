import streamlit as st
import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta, date

# Import the CP-SAT solver from OR-Tools.
from ortools.sat.python import cp_model

# =============================================================================
# LANGUAGE SELECTION & TRANSLATION DICTIONARY
# =============================================================================

language = st.radio("Select Language / Selecciona Idioma", options=["English", "Español"])

translations = {
    "en": {
        "title": "Nurse Shift Scheduling Wheel (Rotation Model)",
        "description": """
This app creates a 12‑week cyclical schedule for 12 nurses—with a twist. Instead of assigning a full 84‑day schedule to each nurse independently, we generate one master 84‑day schedule (covering 12 weeks) and then assign each nurse a cyclic rotation of that schedule. In other words:

- **Nurse Week 1:** Uses the master schedule as-is.
- **Nurse Week 2:** Uses the master schedule shifted by 7 days.
- **… etc.**

All the original constraints are maintained:
- **Daily staffing:** Exactly **3 Day shifts** and **2 Night shifts** per day overall.
- **At most one shift per day** per nurse.
- **No more than 3 consecutive work days** (any block of 4 days has at most 3 shifts).
- **Weekend pairing:** If a nurse works Saturday then Sunday must be worked (and vice‑versa).
- **Rest after a Night shift:** A Night shift cannot be immediately followed by a Day shift.
- **Maximum consecutive off‑shifts:** In any 5‑day block at least one shift must be worked (i.e. no more than 9 off‑shift periods).
- **Fair distribution:** Each nurse works exactly **35 shifts** in 84 days.
        """,
        "schedule_settings": "Schedule Settings",
        "select_date": "Select the schedule start date",
        "enforce_max_rest": "Enforce maximum consecutive off‑shift periods (9 off‑shifts) constraint",
        "nurse_info": "Step 1. Enter Nurse Names (12 total)",
        "nurse_week": "Nurse Week {num} Name",
        "generate_schedule": "Generate Schedule",
        "building_schedule": "Building schedule – please wait...",
        "error_12": "Please enter a name for each of the 12 nurses.",
        "schedule_generated": "Schedule generated successfully!",
        "no_schedule": "No feasible schedule was found. Please adjust parameters and try again.",
        "overall_schedule": "Overall Schedule Grid",
        "personal_schedule_view": "Personal Schedule View",
        "select_nurse": "Select Nurse",
        "legend": """**Legend:**
- **D:** Day shift (12 hours)
- **N:** Night shift (12 hours)
- **Blank:** Off day""",
        "shift_exchange": "Shift Exchange",
        "shift_exchange_desc": "Select two cells to exchange their assignments. The exchange is allowed even if one cell is empty (an off day), so you can swap a shift for a day off.",
        "select_cell_A": "Select Cell A",
        "nurse_A": "Nurse A",
        "day_A": "Day A (select the day index)",
        "select_cell_B": "Select Cell B",
        "nurse_B": "Nurse B",
        "day_B": "Day B (select the day index)",
        "exchange_button": "Exchange Shifts",
        "exchange_success": "Exchanged {nurse_a}'s assignment on day {day_a_index} with {nurse_b}'s assignment on day {day_b_index}.",
    },
    "es": {
        "title": "Rueda de Turnos de Enfermería (Modelo Rotativo)",
        "description": """
Esta aplicación crea un horario cíclico de 12 semanas para 12 enfermeras, pero con un giro. En lugar de asignar un horario completo de 84 días a cada enfermera de forma independiente, generamos un horario maestro de 84 días (cubriendo 12 semanas) y luego asignamos a cada enfermera una rotación cíclica de ese horario. En otras palabras:

- **Semana 1 de Enfermeras:** Usa el horario maestro tal como está.
- **Semana 2 de Enfermeras:** Usa el horario maestro desplazado 7 días.
- **… etc.**

Se mantienen todas las restricciones originales:
- **Plantilla diaria:** Se realizan exactamente **3 turnos de día** y **2 turnos de noche** cada día.
- **Máximo de un turno por día** para cada enfermera.
- **No más de 3 días consecutivos de trabajo** (cualquier bloque de 4 días tiene máximo 3 turnos).
- **Emparejamiento de fines de semana:** Si una enfermera trabaja el sábado, el domingo siguiente debe trabajarse (y viceversa).
- **Descanso tras un turno de noche:** Un turno de noche no puede ir seguido inmediatamente de un turno de día.
- **Máximo de días consecutivos sin turno:** En cualquier bloque de 5 días se debe trabajar al menos un turno (es decir, no más de 9 períodos sin turno).
- **Distribución equitativa:** Cada enfermera trabaja exactamente **35 turnos** en 84 días.
        """,
        "schedule_settings": "Configuración del Horario",
        "select_date": "Selecciona la fecha de inicio del horario",
        "enforce_max_rest": "Aplicar restricción de máximo períodos consecutivos sin turno (9 períodos sin turno)",
        "nurse_info": "Paso 1. Ingresa los nombres de las enfermeras (12 en total)",
        "nurse_week": "Nombre de la Enfermera de la Semana {num}",
        "generate_schedule": "Generar Horario",
        "building_schedule": "Generando el horario, por favor espera...",
        "error_12": "Por favor, ingresa un nombre para cada una de las 12 enfermeras.",
        "schedule_generated": "¡Horario generado exitosamente!",
        "no_schedule": "No se encontró un horario factible. Ajusta los parámetros e intenta de nuevo.",
        "overall_schedule": "Cuadrícula del Horario General",
        "personal_schedule_view": "Vista Personal del Horario",
        "select_nurse": "Selecciona la Enfermera",
        "legend": """**Leyenda:**
- **D:** Turno de Día (12 horas)
- **N:** Turno de Noche (12 horas)
- **En Blanco:** Día libre""",
        "shift_exchange": "Intercambio de Turnos",
        "shift_exchange_desc": "Selecciona dos celdas para intercambiar sus asignaciones. El intercambio es permitido incluso si una celda está vacía (día libre), de modo que puedes cambiar un turno por un día libre.",
        "select_cell_A": "Selecciona la Celda A",
        "nurse_A": "Enfermera A",
        "day_A": "Día A (selecciona el índice del día)",
        "select_cell_B": "Selecciona la Celda B",
        "nurse_B": "Enfermera B",
        "day_B": "Día B (selecciona el índice del día)",
        "exchange_button": "Intercambiar Turnos",
        "exchange_success": "Se intercambió el turno de {nurse_a} en el día {day_a_index} con el turno de {nurse_b} en el día {day_b_index}.",
    }
}

lang_code = "es" if language == "Español" else "en"
t = translations[lang_code]

# =============================================================================
# APP HEADER & DESCRIPTION
# =============================================================================

st.title(t["title"])
st.markdown(t["description"])

# =============================================================================
# SESSION STATE INITIALIZATION
# =============================================================================

if "master_schedule" not in st.session_state:
    st.session_state.master_schedule = None
if "nurse_names" not in st.session_state:
    st.session_state.nurse_names = None
if "start_date" not in st.session_state:
    st.session_state.start_date = None

# =============================================================================
# SCHEDULE SETTINGS & NURSE NAMES INPUT
# =============================================================================

st.header(t["schedule_settings"])

num_weeks = 12
days_per_week = 7
horizon = num_weeks * days_per_week  # 84 days

start_date = st.date_input(t["select_date"], value=date.today())
enforce_max_rest = st.checkbox(t["enforce_max_rest"], value=True)

st.header(t["nurse_info"])
nurse_names = []
for i in range(12):
    nurse_name = st.text_input(t["nurse_week"].format(num=i+1), key=f"name_{i}")
    nurse_names.append(nurse_name.strip())

# =============================================================================
# SCHEDULE GENERATION USING OR-TOOLS (MASTER SCHEDULE + ROTATION)
# =============================================================================

if st.button(t["generate_schedule"]):
    valid_names = [name for name in nurse_names if name != ""]
    if len(valid_names) != 12:
        st.error(t["error_12"])
    else:
        st.info(t["building_schedule"])

        required_day_shifts = 3
        required_night_shifts = 2
        model = cp_model.CpModel()

        # Create master schedule decision variables: y[d, s] for d in 0..83 and s in {0,1}.
        y = {}
        for d in range(horizon):
            for s in [0, 1]:
                y[d, s] = model.NewBoolVar(f"y_d{d}_s{s}")

        # (1) At most one shift per day.
        for d in range(horizon):
            model.Add(y[d, 0] + y[d, 1] <= 1)

        # (2) Fair distribution: exactly 35 shifts in 84 days.
        model.Add(sum(y[d, 0] + y[d, 1] for d in range(horizon)) == 35)

        # (3) Daily staffing constraints per weekday (each residue class modulo 7):
        for r in range(7):
            group = [r + 7 * w for w in range(num_weeks) if r + 7 * w < horizon]
            model.Add(sum(y[d, 0] for d in group) == required_day_shifts)
            model.Add(sum(y[d, 1] for d in group) == required_night_shifts)

        # Helper function for rotation.
        def master_index(n, d):
            return (d - n * days_per_week) % horizon

        # (4) Nurse-specific constraints applied via the rotated master schedule.
        for n in range(12):
            # (4a) No more than 3 consecutive work days.
            for d in range(horizon - 3):
                indices = [master_index(n, d+i) for i in range(4)]
                model.Add(sum(y[idx, 0] + y[idx, 1] for idx in indices) <= 3)
            # (4b) Rest after a Night shift.
            for d in range(horizon - 1):
                model.Add(y[master_index(n, d), 1] + y[master_index(n, d+1), 0] <= 1)
            # (4c) Weekend pairing: Saturday and the following Sunday must be both worked or both off.
            for d in range(horizon - 1):
                nurse_day = start_date + timedelta(days=n * days_per_week + d)
                if nurse_day.weekday() == 5:  # Saturday
                    next_day = nurse_day + timedelta(days=1)
                    if next_day.weekday() == 6:
                        model.Add(
                            y[master_index(n, d), 0] + y[master_index(n, d), 1]
                            ==
                            y[master_index(n, d+1), 0] + y[master_index(n, d+1), 1]
                        )
            # (4d) Maximum consecutive off–shift periods.
            if enforce_max_rest:
                for d in range(horizon - 4):
                    indices = [master_index(n, d+i) for i in range(5)]
                    model.Add(sum(y[idx, 0] + y[idx, 1] for idx in indices) >= 1)

        # (5) Introduce randomness.
        rand_obj = []
        for d in range(horizon):
            for s in [0, 1]:
                coeff = random.randint(0, 10)
                rand_obj.append(coeff * y[d, s])
        model.Maximize(sum(rand_obj))

        # Solve.
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 60.0
        solver.parameters.random_seed = random.randint(0, 1000000)
        status = solver.Solve(model)

        if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            st.success(t["schedule_generated"])
            master_pattern = []
            for d in range(horizon):
                if solver.Value(y[d, 0]) == 1:
                    master_pattern.append("D")
                elif solver.Value(y[d, 1]) == 1:
                    master_pattern.append("N")
                else:
                    master_pattern.append("")
            st.session_state.master_schedule = master_pattern
            st.session_state.nurse_names = valid_names
            st.session_state.start_date = start_date
        else:
            st.error(t["no_schedule"])

# =============================================================================
# OPTIONAL: SHIFT EXCHANGE FEATURE
# =============================================================================

if st.session_state.get("master_schedule") is not None:
    st.header(t["shift_exchange"])
    st.markdown(t["shift_exchange_desc"])

    valid_names = st.session_state.nurse_names
    schedule_dates = [start_date + timedelta(days=d) for d in range(horizon)]
    master_pattern = st.session_state.master_schedule

    # Build the overall schedule grid (using rotation).
    overall_schedule = np.empty((horizon, 12), dtype=object)
    for d in range(horizon):
        for n in range(12):
            idx = (d - n * days_per_week) % horizon
            overall_schedule[d, n] = master_pattern[idx]

    day_options = [f"{i}: {(start_date + timedelta(days=i)).strftime('%b %d (%a)')}" for i in range(horizon)]

    st.subheader(t["select_cell_A"])
    nurse_a = st.selectbox(t["nurse_A"], valid_names, key="nurse_a")
    day_a_option = st.selectbox(t["day_A"], day_options, key="day_a")
    day_a_index = int(day_a_option.split(":")[0])

    st.subheader(t["select_cell_B"])
    nurse_b = st.selectbox(t["nurse_B"], valid_names, key="nurse_b")
    day_b_option = st.selectbox(t["day_B"], day_options, key="day_b")
    day_b_index = int(day_b_option.split(":")[0])

    if st.button(t["exchange_button"]):
        try:
            nurse_a_index = valid_names.index(nurse_a)
            nurse_b_index = valid_names.index(nurse_b)
        except ValueError:
            st.error("Nurse name not found in the list." if lang_code=="en" else "Nombre de enfermera no encontrado en la lista.")
        else:
            cell_a = overall_schedule[day_a_index, nurse_a_index]
            cell_b = overall_schedule[day_b_index, nurse_b_index]
            if cell_a == "" and cell_b == "":
                st.error("Both selected cells are off days; nothing to exchange." if lang_code=="en" else "Ambas celdas seleccionadas son días libres; no hay nada para intercambiar.")
            else:
                overall_schedule[day_a_index, nurse_a_index] = cell_b
                overall_schedule[day_b_index, nurse_b_index] = cell_a
                st.success(t["exchange_success"].format(nurse_a=nurse_a, day_a_index=day_a_index,
                                                          nurse_b=nurse_b, day_b_index=day_b_index))
                # Note: Updating the master schedule consistently requires more logic.

# =============================================================================
# DISPLAY THE SCHEDULE: OVERALL GRID OR PERSONAL VIEW
# =============================================================================

if st.session_state.get("master_schedule") is not None:
    master_pattern = st.session_state.master_schedule
    valid_names = st.session_state.nurse_names
    start_date = st.session_state.start_date
    overall_dates = [start_date + timedelta(days=d) for d in range(horizon)]

    st.markdown("---")
    view_option = st.radio(t["overall_schedule"] + " / " + t["personal_schedule_view"],
                           (t["overall_schedule"], t["personal_schedule_view"]))

    if view_option == t["overall_schedule"]:
        st.subheader(t["overall_schedule"])
        date_labels = [dt.strftime("%b %d (%a)") for dt in overall_dates]
        df_overall = pd.DataFrame(overall_schedule, index=date_labels, columns=valid_names)
        st.dataframe(df_overall.style.set_properties(**{"text-align": "center"}))
        st.markdown(t["legend"])
    else:
        st.subheader(t["personal_schedule_view"])
        selected_nurse = st.selectbox(t["select_nurse"], valid_names)
        nurse_index = valid_names.index(selected_nurse)
        nurse_start = start_date + timedelta(days=nurse_index * days_per_week)
        nurse_dates = [nurse_start + timedelta(days=d) for d in range(horizon)]
        nurse_schedule = []
        for d in range(horizon):
            idx = (d - nurse_index * days_per_week) % horizon
            nurse_schedule.append(master_pattern[idx])
        df_nurse = pd.DataFrame({
            "Date": nurse_dates,
            "Shift": nurse_schedule
        })
        # Convert to datetime so we can use .dt accessor.
        df_nurse["Date"] = pd.to_datetime(df_nurse["Date"])
        df_nurse["Week Start"] = df_nurse["Date"].apply(lambda d: d - timedelta(days=d.weekday()))
        df_nurse["Weekday"] = df_nurse["Date"].dt.day_name()
        pivot = df_nurse.pivot(index="Week Start", columns="Weekday", values="Shift")
        weekday_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        pivot = pivot.reindex(columns=weekday_order)
        pivot.index = [f"Week {i+1}" for i in range(len(pivot))]
        st.dataframe(pivot.style.set_properties(**{"text-align": "center"}))
        st.markdown(t["legend"])