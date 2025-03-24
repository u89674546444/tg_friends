import os
import json
import logging
import re
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)
from fpdf import FPDF

# Состояния для ConversationHandler
(
    SELECTING_HOUSE,
    SELECTING_ADDRESS,
    CONFIRMING_ADDRESS,
    SELECTING_WORK_TYPE,
    CONFIRMING_WORK_TYPE,
    RECEIVING_PHOTO_BEFORE,
    CHOOSING_ACTION,
    RECEIVING_TASK_NUMBER,
    RECEIVING_PHOTO_AFTER,
) = range(9)

# Путь к словарю с домами
HOUSES_DICT_PATH = "/Users/nikolajusakov/PycharmProjects/PythonProject/dic_houses.json"
# Путь к файлу с списком работ
WORKS_LIST_PATH = "/Users/nikolajusakov/PycharmProjects/PythonProject/list_works.json"

# Загрузка словаря с домами
with open(HOUSES_DICT_PATH, "r", encoding="utf-8") as f:
    HOUSES_DICT = json.load(f)

# Загрузка списка работ
with open(WORKS_LIST_PATH, "r", encoding="utf-8") as f:
    LIST_WORKS = json.load(f)

# Кнопки
ACTION_KEYBOARD = [["Добавить фото выполненной работы", "Добавить фото позже"]]
CONTINUE_KEYBOARD = [["Продолжить не выполненную работу", "Начать новую"]]

# Путь к шрифту
FONT_PATH = "/Users/nikolajusakov/PycharmProjects/PythonProject/dejavu-fonts-ttf-2.37/ttf/DejaVuSans.ttf"

# Проверка наличия шрифта
if not os.path.exists(FONT_PATH):
    print(f"Шрифт {FONT_PATH} не найден. Убедитесь, что файл находится в указанной директории.")
    exit(1)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Константа для количества задач на странице
ITEMS_PER_PAGE = 30

# Функция для нормализации ввода
def normalize_input(text):
    """Нормализует ввод пользователя: удаляет знаки препинания и приводит к верхнему регистру."""
    text = re.sub(r"[^\w\s]", "", text)
    text = text.upper()
    return text

# Функция для создания директории отчета
def create_report_directory(house_number):
    """Создает директорию для отчета на основе полного названия адреса."""
    if house_number not in HOUSES_DICT:
        raise ValueError(f"Дом с номером {house_number} не найден в словаре HOUSES_DICT.")

    full_address = HOUSES_DICT[house_number][0]
    now = datetime.now()
    year = now.strftime("%Y")
    month = now.strftime("%m")
    base_dir = os.path.join("reports", year, full_address, month)

    report_number = 1
    while os.path.exists(os.path.join(base_dir, f"report_{report_number}")):
        report_number += 1

    report_dir = os.path.join(base_dir, f"report_{report_number}")
    os.makedirs(report_dir, exist_ok=True)
    logger.info(f"Директория создана: {report_dir}")
    return report_dir

def get_unfinished_tasks():
    base_dir = "reports"
    unfinished_tasks = []

    for root, _, files in os.walk(base_dir):
        for file in files:
            if file == "report.txt":
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                        if "не выполнено" in content:
                            lines = content.split("\n")
                            if len(lines) >= 2:
                                house_number = lines[0].split(": ")[1].strip()
                                work_type = lines[1].split(": ")[1].strip()
                                unfinished_tasks.append({
                                    "house": house_number,
                                    "work_type": work_type,
                                    "path": root
                                })
                            logger.info(f"Найдена незавершенная задача: Дом №{house_number}, Тип работ: {work_type}")
                except Exception as e:
                    logger.error(f"Ошибка при чтении файла {file_path}: {e}")

    logger.info(f"Всего найдено незавершенных задач: {len(unfinished_tasks)}")
    return unfinished_tasks

def create_task_keyboard(page: int = 0):
    tasks = get_unfinished_tasks()
    start = page * ITEMS_PER_PAGE
    end = start + ITEMS_PER_PAGE
    paginated_tasks = tasks[start:end]

    keyboard = []
    for i, task in enumerate(paginated_tasks, start=1):
        # Упрощаем callback_data, используя только house и work_type
        callback_data = f"task_{task['house']}_{task['work_type']}"
        keyboard.append([InlineKeyboardButton(
            f"{i}. Дом №{task['house']}, Тип работ: {task['work_type']}",
            callback_data=callback_data
        )])

    pagination_buttons = []
    if page > 0:
        pagination_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"prev_{page}"))
    if len(tasks) > (page + 1) * ITEMS_PER_PAGE:
        pagination_buttons.append(InlineKeyboardButton("Вперед ➡️", callback_data=f"next_{page}"))

    if pagination_buttons:
        keyboard.append(pagination_buttons)

    return InlineKeyboardMarkup(keyboard)

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите номер дома:")
    return SELECTING_HOUSE

# Обработчик выбора дома
async def select_house(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        await update.message.reply_text("Пожалуйста, введите номер дома, а не фото.")
        return SELECTING_HOUSE

    house_number = normalize_input(update.message.text.strip())
    logger.info(f"Пользователь ввел номер дома: {house_number}")

    if house_number not in HOUSES_DICT:
        available_houses = ", ".join(HOUSES_DICT.keys())
        await update.message.reply_text(
            f"Дом с номером {house_number} не найден. Доступные номера домов: {available_houses}.\n"
            "Пожалуйста, введите другой номер."
        )
        return SELECTING_HOUSE

    context.user_data["selected_house"] = house_number
    context.user_data["addresses"] = HOUSES_DICT[house_number]
    context.user_data["full_address"] = HOUSES_DICT[house_number][0]

    response = "Выберите адрес, введите соответствующую адресу цифру:\n"
    for i, address in enumerate(HOUSES_DICT[house_number], start=1):
        response += f"{i}. {address}\n"

    await update.message.reply_text(response)
    return SELECTING_ADDRESS

# Обработчик выбора адреса
async def select_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        await update.message.reply_text("Пожалуйста, введите цифру, а не фото.")
        return SELECTING_ADDRESS

    try:
        choice = int(update.message.text.strip())
        addresses = context.user_data["addresses"]

        if choice < 1 or choice > len(addresses):
            await update.message.reply_text("Неверный выбор. Пожалуйста, выберите номер из списка.")
            return SELECTING_ADDRESS

        selected_address = addresses[choice - 1]
        context.user_data["selected_address"] = selected_address

        keyboard = [
            [InlineKeyboardButton("Верно", callback_data="correct")],
            [InlineKeyboardButton("Выбрать другой", callback_data="incorrect")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"Выбранный вами адрес: {selected_address}",
            reply_markup=reply_markup
        )
        return CONFIRMING_ADDRESS
    except ValueError:
        await update.message.reply_text("Пожалуйста, введите число.")
        return SELECTING_ADDRESS

# Обработчик подтверждения адреса
async def handle_address_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    if data == "correct":
        if not LIST_WORKS:
            await query.edit_message_text("Список работ пуст. Пожалуйста, проверьте файл list_works.json.")
            return ConversationHandler.END

        response = "Выберите тип работ:\n"
        for i, work in enumerate(LIST_WORKS, start=1):
            response += f"{i}. {work['Наименование']}\n"

        if len(response) > 4096:
            await send_long_message(context, query.message.chat_id, response)
        else:
            await query.edit_message_text(response)

        return SELECTING_WORK_TYPE
    elif data == "incorrect":
        await query.edit_message_text("Введите номер дома:")
        return SELECTING_HOUSE

# Функция для отправки длинных сообщений
async def send_long_message(context, chat_id, text):
    for i in range(0, len(text), 4096):
        await context.bot.send_message(chat_id=chat_id, text=text[i:i + 4096])

# Обработчик выбора типа работ
async def select_work_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text.strip()  # Получаем ввод пользователя и убираем лишние пробелы
    logger.info(f"Пользователь ввел: {user_input}")

    try:
        choice = int(user_input)  # Пробуем преобразовать ввод в число
        if choice < 1 or choice > len(LIST_WORKS):
            await update.message.reply_text(
                f"Неверный выбор. Пожалуйста, выберите число от 1 до {len(LIST_WORKS)}."
            )
            return SELECTING_WORK_TYPE

        selected_work = LIST_WORKS[choice - 1]
        context.user_data["work_type"] = selected_work['Наименование']  # Сохраняем наименование
        context.user_data["work_data"] = selected_work['Данные']  # Сохраняем данные (не используются в выводе)

        # Создаем папку для отчета
        context.user_data["report_dir"] = create_report_directory(context.user_data["selected_house"])

        await update.message.reply_text(f"Вы выбрали тип работ: {selected_work['Наименование']}\nПришлите фото до начала работ.")
        return RECEIVING_PHOTO_BEFORE
    except ValueError:
        await update.message.reply_text("Пожалуйста, введите число.")
        return SELECTING_WORK_TYPE

# Обработчик получения фото "до начала работ"
async def handle_photo_before(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("Пожалуйста, отправьте фото.")
        return RECEIVING_PHOTO_BEFORE

    photo = update.message.photo[-1]
    file = await photo.get_file()

    report_dir = context.user_data["report_dir"]
    photo_before_path = os.path.join(report_dir, "до.jpg")

    try:
        await file.download_to_drive(photo_before_path)
        logger.info(f"Фото 'до начала работ' успешно сохранено: {photo_before_path}")
    except Exception as e:
        logger.error(f"Ошибка при сохранении фото 'до начала работ': {e}")
        await update.message.reply_text("Ошибка при сохранении фото. Пожалуйста, попробуйте еще раз.")
        return RECEIVING_PHOTO_BEFORE

    context.user_data["photo_before"] = photo_before_path

    # Создаем файл report.txt
    text_file_path = os.path.join(report_dir, "report.txt")
    try:
        with open(text_file_path, "w", encoding="utf-8") as f:
            f.write(f"Номер дома: {context.user_data['selected_house']}\n")
            f.write(f"Тип работ: {context.user_data['work_type']}\n")
            f.write(f"Данные: {context.user_data['work_data']}\n")
            f.write("Статус: не выполнено\n")  # По умолчанию статус "не выполнено"
        logger.info(f"Файл report.txt создан: {text_file_path}")
    except Exception as e:
        logger.error(f"Ошибка при создании файла report.txt: {e}")
        await update.message.reply_text("Ошибка при создании отчета. Пожалуйста, попробуйте еще раз.")
        return ConversationHandler.END

    reply_markup = ReplyKeyboardMarkup(ACTION_KEYBOARD, one_time_keyboard=True)
    await update.message.reply_text("Выберите действие:", reply_markup=reply_markup)
    return CHOOSING_ACTION

async def choose_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_choice = update.message.text

    if user_choice == "Добавить фото выполненной работы":
        await update.message.reply_text("Пришлите фото выполненной работы.")
        return RECEIVING_PHOTO_AFTER
    elif user_choice == "Добавить фото позже":
        await update.message.reply_text("Статус задачи обновлен. Выберите следующее действие.")
        reply_markup = ReplyKeyboardMarkup(CONTINUE_KEYBOARD, one_time_keyboard=True)
        await update.message.reply_text("Выберите действие:", reply_markup=reply_markup)
        return CHOOSING_ACTION
    elif user_choice == "Продолжить не выполненную работу":
        try:
            keyboard = create_task_keyboard()
            await update.message.reply_text("Невыполненные задачи:", reply_markup=keyboard)
            return RECEIVING_TASK_NUMBER
        except Exception as e:
            logger.error(f"Ошибка при создании клавиатуры: {e}")
            await update.message.reply_text("Произошла ошибка при создании списка задач. Пожалуйста, попробуйте еще раз.")
            return CHOOSING_ACTION
    elif user_choice == "Начать новую":
        await update.message.reply_text("Начните новую задачу. Введите номер дома.")
        return SELECTING_HOUSE
    else:
        await update.message.reply_text("Неизвестный выбор. Пожалуйста, выберите действие из предложенных.")
        return CHOOSING_ACTION
# Обработчик получения фото "после окончания работ"
async def handle_photo_after(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("Пожалуйста, отправьте фото.")
        return RECEIVING_PHOTO_AFTER

    photo = update.message.photo[-1]
    file = await photo.get_file()

    report_dir = context.user_data.get("report_dir")
    if not report_dir:
        await update.message.reply_text("Ошибка: папка не найдена.")
        return ConversationHandler.END

    photo_after_path = os.path.join(report_dir, "после.jpg")

    try:
        await file.download_to_drive(photo_after_path)
        logger.info("Фото 'после окончания работ' успешно сохранено.")
    except Exception as e:
        logger.error(f"Ошибка при сохранении фото 'после окончания работ': {e}")
        await update.message.reply_text("Ошибка при сохранении фото. Пожалуйста, попробуйте еще раз.")
        return RECEIVING_PHOTO_AFTER

    # Обновляем текстовый документ
    text_file_path = os.path.join(report_dir, "report.txt")
    try:
        with open(text_file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        with open(text_file_path, "w", encoding="utf-8") as f:
            for line in lines:
                if "не выполнено" in line:
                    f.write("Статус: выполнено\n")
                else:
                    f.write(line)

        logger.info(f"Текстовый файл обновлен: {text_file_path}")
    except Exception as e:
        logger.error(f"Ошибка при обновлении текстового файла: {e}")
        await update.message.reply_text("Ошибка при обновлении текстового файла.")
        return ConversationHandler.END

    # Создаем PDF
    pdf = FPDF()
    pdf.add_page()
    pdf.add_font("DejaVu", "", FONT_PATH, uni=True)
    pdf.set_font("DejaVu", size=12)

    # Добавляем текст в PDF
    pdf.cell(200, 10, txt=f"Номер дома: {context.user_data['selected_house']}", ln=True)
    pdf.cell(200, 10, txt=f"Тип работ: {context.user_data['work_type']}", ln=True)
    pdf.cell(200, 10, txt="Статус: выполнено", ln=True)

    # Добавляем фото в PDF
    pdf.image(os.path.join(report_dir, "до.jpg"), x=10, y=50, w=90)
    pdf.image(photo_after_path, x=110, y=50, w=90)

    pdf_output = os.path.join(report_dir, "report.pdf")
    try:
        pdf.output(pdf_output)
        logger.info("PDF успешно создан.")
    except Exception as e:
        logger.error(f"Ошибка при создании PDF: {e}")
        await update.message.reply_text("Ошибка при создании PDF. Пожалуйста, попробуйте еще раз.")
        return ConversationHandler.END

    # Отправляем PDF пользователю
    try:
        with open(pdf_output, "rb") as file:
            await update.message.reply_document(document=file,
                                                caption=f"Отчет для дома №{context.user_data['selected_house']}")
        logger.info("PDF успешно отправлен.")
    except Exception as e:
        logger.error(f"Ошибка при отправке PDF: {e}")
        await update.message.reply_text("Ошибка при отправке PDF.")
        return ConversationHandler.END

    # Получаем список незавершенных задач
    unfinished_tasks = get_unfinished_tasks()
    if unfinished_tasks:
        # Формируем список задач
        response = "Незавершенные задачи:\n"
        for i, task in enumerate(unfinished_tasks, start=1):
            response += f"{i}. Дом №{task['house']}, Тип работ: {task['work_type']}\n"

        # Отправляем список задач пользователю
        await update.message.reply_text(response)
    else:
        await update.message.reply_text("Нет незавершенных задач.")

    # Предлагаем выбрать действие
    reply_markup = ReplyKeyboardMarkup(CONTINUE_KEYBOARD, one_time_keyboard=True)
    await update.message.reply_text("Выберите действие:", reply_markup=reply_markup)
    logger.info("Кнопки для выбора действия отправлены пользователю.")

    return CHOOSING_ACTION

# Обработчик подтверждения типа работ
async def handle_work_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    if data == "work_correct":
        # Получаем выбранный тип работ
        selected_work = context.user_data.get("work_type")

        # Отправляем только наименование
        await query.edit_message_text(f"Тип работ подтвержден: {selected_work}\nПришлите фото до начала работ.")
        return RECEIVING_PHOTO_BEFORE
    elif data == "work_incorrect":
        # Если выбор неверен, возвращаемся к выбору типа работ
        await query.edit_message_text("Выберите тип работ заново:")
        return SELECTING_WORK_TYPE

# Обработчик выбора задачи из списка незавершенных
async def handle_task_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    if data.startswith("task_"):
        _, house, work_type = data.split("_")
        context.user_data["selected_house"] = house
        context.user_data["work_type"] = work_type
        await query.edit_message_text(f"Выбрана задача: Дом №{house}, Тип работ: {work_type}")
        return RECEIVING_PHOTO_AFTER
    elif data.startswith("prev_") or data.startswith("next_"):
        action, page = data.split("_")
        page = int(page)
        new_page = page - 1 if action == "prev" else page + 1

        # Обновляем сообщение с новыми кнопками
        keyboard = create_task_keyboard(new_page)
        await query.edit_message_text("Невыполненные задачи:", reply_markup=keyboard)
        return RECEIVING_TASK_NUMBER

# Основная функция для запуска бота
def main():
    application = ApplicationBuilder().token('8127498518:AAFzskJYwY0-gkF2FdjJbtY1YcjZVd88wGs').build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SELECTING_HOUSE: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_house)],
            SELECTING_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_address)],
            CONFIRMING_ADDRESS: [CallbackQueryHandler(handle_address_confirmation)],
            SELECTING_WORK_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_work_type)],
            CONFIRMING_WORK_TYPE: [CallbackQueryHandler(handle_work_confirmation)],
            RECEIVING_PHOTO_BEFORE: [MessageHandler(filters.PHOTO, handle_photo_before)],
            CHOOSING_ACTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_action)],
            RECEIVING_TASK_NUMBER: [CallbackQueryHandler(handle_task_selection)],
            RECEIVING_PHOTO_AFTER: [MessageHandler(filters.PHOTO, handle_photo_after)],
        },
        fallbacks=[CommandHandler("start", start)],
    )

    application.add_handler(conv_handler)
    application.run_polling()

if __name__ == '__main__':
    main()