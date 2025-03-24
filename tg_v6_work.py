import os
import json
import logging
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
    RECEIVING_PHOTO_BEFORE,
    CHOOSING_ACTION,
    RECEIVING_TASK_NUMBER,
    RECEIVING_PHOTO_AFTER,
) = range(8)

# Путь к словарю с домами
HOUSES_DICT_PATH = "/Users/nikolajusakov/PycharmProjects/PythonProject/dic_houses.json"

# Загрузка словаря с домами
with open(HOUSES_DICT_PATH, "r", encoding="utf-8") as f:
    HOUSES_DICT = json.load(f)

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


# Функция для создания структуры каталогов
def create_report_directory(house):
    now = datetime.now()
    year = now.strftime("%Y")
    month = now.strftime("%m")
    base_dir = os.path.join("reports", year, house, month)

    # Находим последний номер отчета
    report_number = 1
    while os.path.exists(os.path.join(base_dir, f"report_{report_number}")):
        report_number += 1

    report_dir = os.path.join(base_dir, f"report_{report_number}")
    os.makedirs(report_dir, exist_ok=True)
    logger.info(f"Директория создана: {report_dir}")
    return report_dir


# Обработчик для inline-кнопок
async def handle_inline_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # Подтверждаем нажатие кнопки

    if query.data == "correct":
        await query.edit_message_text("Адрес подтвержден. Теперь выберите тип работ.")
        return SELECTING_WORK_TYPE
    elif query.data == "incorrect":
        await query.edit_message_text("Введите номер дома:")
        return SELECTING_HOUSE


# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите номер дома:")
    return SELECTING_HOUSE


# Обработчик выбора дома
async def select_house(update: Update, context: ContextTypes.DEFAULT_TYPE):
    house_number = update.message.text.strip()  # Убираем лишние пробелы
    logger.info(f"Пользователь ввел номер дома: {house_number}")

    # Проверяем, есть ли такой номер дома в словаре
    if house_number not in HOUSES_DICT:
        available_houses = ", ".join(HOUSES_DICT.keys())
        await update.message.reply_text(
            f"Дом с номером {house_number} не найден. Доступные номера домов: {available_houses}.\n"
            "Пожалуйста, введите другой номер."
        )
        return SELECTING_HOUSE  # Остаемся в состоянии выбора дома

    # Если номер дома найден, переходим к выбору адреса
    addresses = HOUSES_DICT[house_number]
    context.user_data["addresses"] = addresses
    context.user_data["selected_house"] = house_number

    # Формируем нумерованный список адресов
    response = "Выберите адрес:\n"
    for i, address in enumerate(addresses, start=1):
        response += f"{i}. {address}\n"

    await update.message.reply_text(response)
    logger.info(f"Переход к состоянию SELECTING_ADDRESS")
    return SELECTING_ADDRESS  # Переходим к состоянию выбора адреса


# Обработчик выбора адреса
async def select_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        choice = int(update.message.text.strip())  # Убираем лишние пробелы и преобразуем в число
        addresses = context.user_data["addresses"]

        if choice < 1 or choice > len(addresses):
            await update.message.reply_text("Неверный выбор. Пожалуйста, выберите номер из списка.")
            return SELECTING_ADDRESS

        selected_address = addresses[choice - 1]
        context.user_data["selected_address"] = selected_address

        # Создаем inline-кнопки
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


# Обработчик подтверждения выбора адреса
async def handle_address_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_choice = update.message.text

    if user_choice == "Верно":
        await update.message.reply_text("Адрес подтвержден. Теперь выберите тип работ.")
        return SELECTING_WORK_TYPE
    elif user_choice == "Выбрать другой":
        await update.message.reply_text("Введите номер дома:")
        return SELECTING_HOUSE


# Обработчик ввода типа работ
async def select_work_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    work_type = update.message.text
    context.user_data["work_type"] = work_type
    await update.message.reply_text("Пришлите фото до начала работ.")
    return RECEIVING_PHOTO_BEFORE


# Обработчик получения фото "до начала работ"
async def handle_photo_before(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    file = await photo.get_file()

    # Создаем папку для отчета и сохраняем путь в context.user_data
    if "report_dir" not in context.user_data:
        context.user_data["report_dir"] = create_report_directory(context.user_data["selected_house"])

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

    # Отправляем кнопки
    reply_markup = ReplyKeyboardMarkup(ACTION_KEYBOARD, one_time_keyboard=True)
    await update.message.reply_text("Выберите действие:", reply_markup=reply_markup)

    return CHOOSING_ACTION


# Обработчик выбора действия
async def choose_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_choice = update.message.text

    if user_choice == "Добавить фото выполненной работы":
        await update.message.reply_text("Пришлите фото выполненной работы.")
        return RECEIVING_PHOTO_AFTER
    elif user_choice == "Добавить фото позже":
        await update.message.reply_text("Фото будет добавлено позже. Начните новую задачу.")
        return SELECTING_HOUSE


# Обработчик получения фото "после окончания работ"
async def handle_photo_after(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Начало обработки фото 'после окончания работ'.")

    photo = update.message.photo[-1]
    file = await photo.get_file()

    report_dir = context.user_data.get("report_dir")
    if not report_dir:
        logger.error("Ошибка: папка не найдена.")
        await update.message.reply_text("Ошибка: папка не найдена.")
        return ConversationHandler.END

    photo_after_path = os.path.join(report_dir, "после.jpg")
    logger.info(f"Путь для сохранения фото: {photo_after_path}")

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
        with open(text_file_path, "w", encoding="utf-8") as f:
            f.write(f"Номер дома: {context.user_data['selected_house']}\n")
            f.write(f"Тип работ: {context.user_data['work_type']}\n")
            f.write("Статус: выполнено\n")
        logger.info("Текстовый файл успешно обновлен.")
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
            await update.message.reply_document(document=file, caption=f"Отчет для дома №{context.user_data['selected_house']}")
        logger.info("PDF успешно отправлен.")
    except Exception as e:
        logger.error(f"Ошибка при отправке PDF: {e}")
        await update.message.reply_text("Ошибка при отправке PDF.")
        return ConversationHandler.END

    # Создаем новую папку для следующих файлов
    context.user_data["report_dir"] = create_report_directory(context.user_data["selected_house"])
    await update.message.reply_text("Папка заполнена. Начните новую задачу. Введите номер дома.")
    return SELECTING_HOUSE


# Основная функция
def main():
    application = ApplicationBuilder().token('8127498518:AAFzskJYwY0-gkF2FdjJbtY1YcjZVd88wGs').build()  # Замените на ваш токен

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SELECTING_HOUSE: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_house)],
            SELECTING_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_address)],
            CONFIRMING_ADDRESS: [
                CallbackQueryHandler(handle_inline_buttons),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_address_confirmation)
            ],
            SELECTING_WORK_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_work_type)],
            RECEIVING_PHOTO_BEFORE: [MessageHandler(filters.PHOTO, handle_photo_before)],
            CHOOSING_ACTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_action)],
            RECEIVING_PHOTO_AFTER: [MessageHandler(filters.PHOTO, handle_photo_after)],
        },
        fallbacks=[],
    )

    application.add_handler(conv_handler)
    application.run_polling()


if __name__ == '__main__':
    main()