import calendar
import json
import os
from datetime import datetime, timedelta
import streamlit as st

# Настройка страницы для мобильных устройств
st.set_page_config(
    page_title="HET Billing — Premium Edition",
    page_icon="⚡",
    layout="wide",
)

# База данных для сохранения истории
db_file = "billing_history.json"

# Конфигурация тарифных периодов
periods = [
    {
        "name": "До 31.05.2024 (Архивный)",
        "start": datetime(2019, 8, 15),
        "end": datetime(2024, 4, 30),
    },
    {
        "name": "01.06.2024 — 30.04.2025",
        "start": datetime(2024, 5, 1),
        "end": datetime(2025, 6, 30),
    },
    {
        "name": "01.05.2025 — 31.05.2026",
        "start": datetime(2025, 7, 1),
        "end": datetime(2026, 7, 31),
    },
    {
        "name": "С 01.08.2026 (Новая сетка)",
        "start": datetime(2026, 8, 1),
        "end": datetime(2030, 1, 1),
    },
]

# Тарифные ставки
tariffs_config = [
    {"end": datetime(2024, 5, 31), "rates": [295.0, 295.0, 295.0, 295.0, 295.0]},
    {"end": datetime(2025, 4, 30), "rates": [450.0, 900.0, 1350.0, 1350.0, 1350.0]},
    {"end": datetime(2026, 5, 31), "rates": [600.0, 800.0, 1000.0, 1500.0, 1500.0]},
    {"end": datetime(2030, 1, 1), "rates": [650.0, 900.0, 1100.0, 1600.0, 2200.0]},
]


def get_rate(date_obj, tier):
    for period in tariffs_config:
        if date_obj <= period["end"]:
            return period["rates"][tier - 1]
    return 650.0


def calculate_month_logic(date_obj, avg_kw_day, days_active, days_in_month):
    month_name = date_obj.strftime("%m.%Y")
    full_month_kw = avg_kw_day * days_in_month
    kw_active = avg_kw_day * days_active

    if date_obj <= datetime(2024, 5, 31):
        cost_active = kw_active * 295.0
        short_line = (
            f"• {month_name} ({days_active}/{days_in_month} дн, {kw_active:.1f}"
            f" кВт·ч) — {cost_active:,.2f} сум\n"
        )
        return (
            cost_active,
            short_line,
            month_name,
            days_active,
            days_in_month,
            kw_active,
        )

    limits_base = [200.0, 300.0, 500.0, 4000.0, 5000.0]
    allocated_full_kw = []
    remainder = full_month_kw
    for lim in limits_base:
        allocated = min(max(remainder, 0.0), lim)
        allocated_full_kw.append(allocated)
        remainder -= allocated
    allocated_full_kw.append(max(remainder, 0.0))

    cost_active = 0.0
    fraction = days_active / days_in_month

    for i in range(len(limits_base) + 1):
        k_full = allocated_full_kw[i]
        k_active = k_full * fraction

        if k_active > 0:
            tier_num = (
                min(i + 1, 3) if date_obj <= datetime(2026, 5, 31) else i + 1
            )
            if i == len(limits_base):
                tier_num = 3 if date_obj <= datetime(2026, 5, 31) else 5
            rate = get_rate(date_obj, tier_num)
            cost_active += k_active * rate

    short_line = (
        f"• {month_name} ({days_active}/{days_in_month} дн, {kw_active:.1f}"
        f" кВт·ч) — {cost_active:,.2f} сум\n"
    )
    return (
        cost_active,
        short_line,
        month_name,
        days_active,
        days_in_month,
        kw_active,
    )


def save_to_history(
    account,
    address,
    period_str,
    kw_str,
    cost_str,
    status_str,
    summary_text,
    payload=None,
):
    new_record = {
        "date": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "account": account,
        "address": address,
        "period": period_str,
        "kw": kw_str,
        "cost": cost_str,
        "status": status_str,
        "summary": summary_text,
        "payload": payload or {},
    }
    data = []
    if os.path.exists(db_file):
        try:
            with open(db_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = []

    data.insert(0, new_record)
    with open(db_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


# Навигация
st.sidebar.title("⚡ HET BILLING")
menu = st.sidebar.radio(
    "Разделы", ["📊 Калькулятор обходов", "📂 Журнал перерасчетов"]
)
st.sidebar.markdown("---")
st.sidebar.info("Версия: 2026.6.12 (Mobile Ready)\nЛогика: Честный календарь")

# СТРАНИЦА: КАЛЬКУЛЯТОР
if menu == "📊 Калькулятор обходов":
    st.title("Панель расчета абонентской платы")

    with st.form("billing_form"):
        col1, col2 = st.columns(2)

        with col1:
            ent_account = st.text_input("Лицевой счет абонента:")
            ent_address = st.text_input("Адрес абонента:")
            ent_d1 = st.text_input("Дата прошл. обхода (ДД.ММ.ГГГГ):")
            ent_d2 = st.text_input("Дата тек. обхода (ДД.ММ.ГГГГ):")

        with col2:
            ent_r1 = st.text_input("Предыдущие показания:")
            ent_r2 = st.text_input("Новые показания:")
            ent_pay = st.text_input("Внесено денег (сум):", value="0")

        submitted = st.form_submit_button("⚡ Выполнить перерасчет")

    if submitted:
        try:
            if not ent_account.strip():
                st.warning("Введите лицевой счет абонента!")
            else:
                d_start = datetime.strptime(ent_d1.strip(), "%d.%m.%Y")
                d_end = datetime.strptime(ent_d2.strip(), "%d.%m.%Y")
                old_r = float(ent_r1.strip())
                new_r = float(ent_r2.strip())
                payment = float(ent_pay.strip()) if ent_pay.strip() else 0.0

                total_kw = new_r - old_r
                total_days = (d_end - d_start).days

                if total_days <= 0:
                    st.error("Конечная дата должна быть позже начальной!")
                else:
                    months_count = total_days / 30.44
                    avg_kw_day = total_kw / total_days

                    summary_periods = {
                        p["name"]: {"days": 0, "kw": 0.0, "cost": 0.0}
                        for p in periods
                    }
                    month_details = []

                    short_summary = (
                        f"СПРАВКА ПО Л/С: {ent_account} | {ent_address}\n"
                    )
                    short_summary += (
                        f"Период: {ent_d1} — {ent_d2} ({total_days}"
                        f" дн.) | Расход: {total_kw:.1f} кВт·ч\n"
                    )
                    short_summary += (
                        "----------------------------------------------------------------------------------\n"
                    )

                    current_date = d_start
                    while current_date < d_end:
                        y, m = current_date.year, current_date.month
                        _, days_in_month = calendar.monthrange(y, m)

                        start_p = max(current_date, datetime(y, m, 1))
                        end_p = min(d_end, datetime(y, m, days_in_month))

                        days_active = (end_p - start_p).days + 1
                        (
                            cost_m,
                            short_line_m,
                            m_name,
                            d_act,
                            d_in_m,
                            kw_m,
                        ) = calculate_month_logic(
                            start_p, avg_kw_day, days_active, days_in_month
                        )

                        short_summary += short_line_m
                        month_details.append(
                            {
                                "month": m_name,
                                "days": f"{d_act}/{d_in_m}",
                                "kw": f"{kw_m:.1f}",
                                "cost": f"{cost_m:,.2f}",
                            }
                        )

                        for p in periods:
                            if p["start"] <= start_p <= p["end"]:
                                summary_periods[p["name"]][
                                    "days"
                                ] += days_active
                                summary_periods[p["name"]]["kw"] += kw_m
                                summary_periods[p["name"]]["cost"] += cost_m
                                break

                        current_date = datetime(y, m, days_in_month) + timedelta(
                            days=1
                        )

                    total_cost = sum(
                        data["cost"] for data in summary_periods.values()
                    )
                    short_summary += (
                        "----------------------------------------------------------------------------------\n"
                    )
                    short_summary += (
                        f"ИТОГО К НАЧИСЛЕНИЮ: {total_cost:,.2f} сум"
                    )

                    balance = payment - total_cost
                    if balance < 0:
                        status_str = f"Долг: {abs(balance):,.2f} сум"
                    else:
                        status_str = f"Предоплата: {balance:,.2f} сум"

                    input_payload = {
                        "d1": ent_d1,
                        "d2": ent_d2,
                        "r1": ent_r1,
                        "r2": ent_r2,
                        "pay": ent_pay,
                        "payment_val": payment,
                        "total_kw": total_kw,
                        "total_days": total_days,
                        "avg_kw_day": avg_kw_day,
                        "month_details": month_details,
                    }

                    save_to_history(
                        ent_account,
                        ent_address,
                        f"{ent_d1} - {ent_d2}",
                        f"{total_kw:,.1f}",
                        f"{total_cost:,.2f}",
                        status_str,
                        short_summary,
                        input_payload,
                    )

                    st.success("Расчет проведен и сохранен!")

                    m1, m2, m3 = st.columns(3)
                    m1.metric(
                        "ОБЩИЙ РАСХОД",
                        f"{total_kw:,.1f} кВт·ч",
                        f"{total_days} дн. ({months_count:.1f} мес.)",
                    )
                    m2.metric(
                        "НАЧИСЛЕНО В СУММАХ", f"{total_cost:,.2f} сум"
                    )
                    m3.metric("ТЕКУЩИЙ БАЛАНС", status_str)

                    st.subheader("📑 Краткая справка начислений")
                    st.text_area("Протокол", short_summary, height=180)

                    st.subheader("📊 Начисления по тарифным периодам")
                    table_data = []
                    for name, data in summary_periods.items():
                        if data["days"] > 0:
                            table_data.append(
                                {
                                    "Тарифный период": name,
                                    "Дней": data["days"],
                                    "Объем (кВт·ч)": f"{data['kw']:.1f}",
                                    "Сумма (сум)": f"{data['cost']:,.2f}",
                                }
                            )
                    st.table(table_data)

        except ValueError:
            st.error("Проверьте правильность введенных чисел и дат (ДД.ММ.ГГГГ).")

# СТРАНИЦА: ЖУРНАЛ
elif menu == "📂 Журнал перерасчетов":
    st.title("Журнал выполненных перерасчетов")

    if not os.path.exists(db_file):
        st.info("Журнал пока пуст.")
    else:
        try:
            with open(db_file, "r", encoding="utf-8") as f:
                records = json.load(f)

            search_query = st.text_input("🔍 Поиск (Л/С или Адрес):")

            filtered_records = []
            for r in records:
                addr = r.get("address", "Не указан")
                if search_query:
                    sq = search_query.lower()
                    if (
                        sq not in r["account"].lower()
                        and sq not in addr.lower()
                    ):
                        continue
                filtered_records.append(r)

            if st.button("🗑️ Очистить журнал"):
                if os.path.exists(db_file):
                    os.remove(db_file)
                st.rerun()

            for idx, r in enumerate(filtered_records):
                with st.expander(
                    f"Л/С: {r['account']} | {r.get('address', 'Не указан')} | {r['cost']} сум"
                ):
                    st.write(f"**Дата операции:** {r['date']}")
                    st.write(f"**Период обхода:** {r['period']}")
                    st.write(f"**Расход:** {r['kw']} кВт·ч")
                    st.write(f"**Статус:** {r['status']}")

                    payload = r.get("payload", {})
                    m_details = payload.get("month_details", [])
                    if m_details:
                        st.write("**Детализация по месяцам:**")
                        st.table(m_details)

                    st.text_area(
                        "Справка",
                        r.get("summary", ""),
                        height=150,
                        key=f"sum_{idx}",
                    )
        except Exception as e:
            st.error(f"Ошибка чтения данных: {e}")
