import os
import json
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)
import openpyxl

# Состояния для ConversationHandler
REQUESTING_PHONE, REQUESTING_FULL_NAME, SELECTING_HOUSE, SELECTING_WORK_TYPE, RECEIVING_PHOTO_BEFORE, RECEIVING_PHOTO_AFTER, CONTINUING_WORK, SELECTING_UNFINISHED_JOB = range(8)

# Путь к Excel-файлам
USERS_EXCEL_PATH = "users.xlsx"
HOUSES_EXCEL_PATH = "Houses.xlsx"
WORKS_EXCEL_PATH = "works.xlsx"
UNFINISHED_JOBS_PATH = "unfinished_jobs.json"

# Проверка и создание необходимых файлов
def initialize_files():
    if not os.path.exists(USERS_EXCEL_PATH):
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.title = "Users"
        sheet.append(["Phone", "Full Name"])
        workbook.save(USERS_EXCEL_PATH)

    if not os.path.exists(UNFINISHED_JOBS_PATH):
        with open(UNFINISHED_JOBS_PATH, "w", encoding="utf-8") as file:
            json.dump({}, file)

initialize_files()

# Функции для работы с данными
def add_unfinished_job(user_id, house_number, full_name, house_full_name, work_type, photo_before):
    try:
        with open(UNFINISHED_JOBS_PATH, "r", encoding="utf-8") as file:
            unfinished_jobs = json.load(file)

        if str(user_id) not in unfinished_jobs:
            unfinished_jobs[str(user_id)] = []

        unfinished_jobs[str(user_id)].append({
            "house_number": house_number,
            "full_name": full_name,
            "house_full_name": house_full_name,
            "work_type": work_type,
            "photo_before": photo_before,
            "status": "В работе"
        })

        with open(UNFINISHED_JOBS_PATH, "w", encoding="utf-8") as file:
            json.dump(unfinished_jobs, file, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Ошибка при добавлении незавершенной работы: {e}")

def get_unfinished_jobs(user_id):
    try:
        with open(UNFINISHED_JOBS_PATH, "r", encoding="utf-8") as file:
            unfinished_jobs = json.load(file)
        return unfinished_jobs.get(str(user_id), [])
    except Exception as e:
        print(f"Ошибка при получении списка незавершенных работ: {e}")
        return []

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    unfinished_jobs = get_unfinished_jobs(user_id)

    if unfinished_jobs:
        jobs_list = "\n".join(
            [f"{i + 1}. {job['work_type']} ({job['house_full_name']})" for i, job in enumerate(unfinished_jobs)]
        )
        await update.message.reply_text(f"Ваши незавершенные работы:\n{jobs_list}\nВведите номер работы для продолжения или нажмите кнопку 'Новая работа' для начала новой работы.")
        keyboard = [[KeyboardButton("Новая работа")], [KeyboardButton("Продолжить работу")]]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        await update.message.reply_text("Выберите действие:", reply_markup=reply_markup)
        return CONTINUING_WORK
    else:
        await update.message.reply_text("У вас нет незавершенных работ. Выберите номер дома:")
        return SELECTING_HOUSE

# Обработчик ввода номера телефона
async def request_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text
    context.user_data["phone"] = phone
    await update.message.reply_text("Введите ваше ФИО:")
    return REQUESTING_FULL_NAME

# Обработчик ввода ФИО
async def request_full_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    full_name = update.message.text
    context.user_data["full_name"] = full_name
    await update.message.reply_text("Авторизация завершена. Выберите номер дома:")
    return SELECTING_HOUSE

# Обработчик выбора дома
async def select_house(update: Update, context: ContextTypes.DEFAULT_TYPE):
    selected_house = update.message.text
    context.user_data["selected_house"] = selected_house
    await update.message.reply_text("Выберите тип работы:")
    return SELECTING_WORK_TYPE

# Обработчик выбора типа работ
async def select_work_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    work_type = update.message.text
    context.user_data["work_type"] = work_type
    await update.message.reply_text("Пришлите фото до начала работ.")
    return RECEIVING_PHOTO_BEFORE

# Обработчик получения фото "до начала работ"
async def handle_photo_before(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Проверяем, есть ли необходимые данные в context.user_data
    if "full_name" not in context.user_data or "selected_house" not in context.user_data or "work_type" not in context.user_data:
        await update.message.reply_text("Ошибка: данные пользователя не найдены. Пожалуйста, начните с команды /start.")
        return ConversationHandler.END

    # Остальная логика функции
    photo = update.message.photo[-1]
    file = await photo.get_file()
    photo_before = f"photo_before_{context.user_data['selected_house']}.jpg"
    await file.download_to_drive(photo_before)
    context.user_data["photo_before"] = photo_before

    add_unfinished_job(
        update.message.from_user.id,
        context.user_data["selected_house"],
        context.user_data["full_name"],
        "House Full Name",  # Замените на реальное название дома
        context.user_data["work_type"],
        photo_before
    )

    await update.message.reply_text("Фото до начала работ сохранено. Пришлите фото после окончания работ.")
    return RECEIVING_PHOTO_AFTER

# Обработчик получения фото "после окончания работ"
async def handle_photo_after(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    file = await photo.get_file()
    photo_after = f"photo_after_{context.user_data['selected_house']}.jpg"
    await file.download_to_drive(photo_after)
    context.user_data["photo_after"] = photo_after

    await update.message.reply_text("Работа завершена. Спасибо!")
    return ConversationHandler.END

# Обработчик продолжения работы
async def continue_work(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    unfinished_jobs = get_unfinished_jobs(user_id)

    if update.message.text == "Новая работа":
        await update.message.reply_text("Выберите номер дома:")
        return SELECTING_HOUSE
    elif update.message.text == "Продолжить работу":
        if unfinished_jobs:
            jobs_list = "\n".join(
                [f"{i + 1}. {job['work_type']} ({job['house_full_name']})" for i, job in enumerate(unfinished_jobs)]
            )
            await update.message.reply_text(
                f"Ваши незавершенные работы:\n{jobs_list}\nВведите номер работы для продолжения:")
            return SELECTING_UNFINISHED_JOB
        else:
            await update.message.reply_text("У вас нет незавершенных работ. Выберите номер дома:")
            return SELECTING_HOUSE

# Обработчик выбора незавершенной работы
async def select_unfinished_job(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    unfinished_jobs = get_unfinished_jobs(user_id)

    try:
        job_index = int(update.message.text) - 1
        if 0 <= job_index < len(unfinished_jobs):
            selected_job = unfinished_jobs[job_index]

            context.user_data["selected_house"] = selected_job["house_number"]
            context.user_data["work_type"] = selected_job["work_type"]
            context.user_data["house_full_name"] = selected_job["house_full_name"]
            context.user_data["photo_before"] = selected_job["photo_before"]

            await update.message.reply_photo(selected_job["photo_before"], caption=f"Продолжаем работу: {context.user_data['work_type']} ({selected_job['house_full_name']})")
            await update.message.reply_text("Пришлите фото после окончания работ.")
            return RECEIVING_PHOTO_BEFORE
        else:
            await update.message.reply_text("Неверный номер работы. Попробуйте снова.")
            return CONTINUING_WORK
    except ValueError:
        await update.message.reply_text("Неверный ввод. Введите номер работы (число).")
        return CONTINUING_WORK

# Основная функция
def main():
    application = Application.builder().token('8127498518:AAFzskJYwY0-gkF2FdjJbtY1YcjZVd88wGs').build()  # Замените на ваш токен

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            REQUESTING_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, request_phone)],
            REQUESTING_FULL_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, request_full_name)],
            SELECTING_HOUSE: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_house)],
            SELECTING_WORK_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_work_type)],
            RECEIVING_PHOTO_BEFORE: [MessageHandler(filters.PHOTO, handle_photo_before)],
            RECEIVING_PHOTO_AFTER: [MessageHandler(filters.PHOTO, handle_photo_after)],
            CONTINUING_WORK: [MessageHandler(filters.TEXT & ~filters.COMMAND, continue_work)],
            SELECTING_UNFINISHED_JOB: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_unfinished_job)],
        },
        fallbacks=[],
    )

    application.add_handler(conv_handler)
    application.run_polling()

if __name__ == '__main__':
    main()