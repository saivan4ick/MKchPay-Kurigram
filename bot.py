import logging
import os
import tempfile
from pyrogram import Client, filters
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    LabeledPrice,
    PreCheckoutQuery,
)
from config import (
    BOT_TOKEN,
    API_HASH,
    API_ID,
    PRICE_STARS,
    PASSCODES_FILE,
    OWNER_ID,
    ADMINS_FILE,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)
app = Client(
    "passcode_bot",
    bot_token=BOT_TOKEN,
    api_id=API_ID,
    api_hash=API_HASH,
)
PRODUCT_TITLE = "ПАССКОД 🔑"
PRODUCT_DESCRIPTION = (
    "Уникальный пасскод для доступа к MKch. "
    "После оплаты вы мгновенно получите ваш пасскод в личном сообщении."
)
PAYLOAD = "passcode_purchase_v1"
processed_charge_ids: set[str] = set()


def register_processed_charge(processed: set[str], charge_id: str) -> bool:
    if charge_id in processed:
        return False
    processed.add(charge_id)
    return True


def is_txt_filename(filename: str | None) -> bool:
    if not filename:
        return False
    return filename.lower().endswith(".txt")


def pop_passcode() -> str | None:
    try:
        with open(PASSCODES_FILE, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        log.error("Файл %s не найден!", PASSCODES_FILE)
        return None

    if not lines:
        return None

    passcode = lines[0]
    remaining = lines[1:]

    with open(PASSCODES_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(remaining) + ("\n" if remaining else ""))

    log.info("Выдан пасскод. Осталось в файле: %d", len(remaining))
    return passcode


def count_passcodes() -> int:
    try:
        with open(PASSCODES_FILE, "r", encoding="utf-8") as f:
            return sum(1 for line in f if line.strip())
    except FileNotFoundError:
        return 0


def get_admins() -> set[int]:
    admins = {OWNER_ID}
    try:
        with open(ADMINS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.isdigit():
                    admins.add(int(line))
    except FileNotFoundError:
        pass
    return admins


def add_admin(user_id: int) -> bool:
    admins = get_admins()
    if user_id in admins:
        return False
    with open(ADMINS_FILE, "a", encoding="utf-8") as f:
        f.write(f"{user_id}\n")
    return True


def append_passcodes_from_file(filepath: str) -> tuple[int, int]:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            new_codes = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        return 0, 0

    try:
        with open(PASSCODES_FILE, "r", encoding="utf-8") as f:
            existing = {line.strip() for line in f if line.strip()}
    except FileNotFoundError:
        existing = set()

    added = 0
    skipped = 0
    with open(PASSCODES_FILE, "a", encoding="utf-8") as f:
        for code in new_codes:
            if code in existing:
                skipped += 1
            else:
                f.write(code + "\n")
                existing.add(code)
                added += 1

    return added, skipped


pending_add_admin: dict[int, bool] = {}
pending_upload: dict[int, bool] = {}


@app.on_message(filters.command("start") & filters.private)
async def cmd_start(client: Client, message: Message):
    stock = count_passcodes()
    stock_text = (
        f"В наличии: **{stock} шт.**" if stock > 0 else "⚠️ Товар временно отсутствует"
    )
    await message.reply(
        f"👋 Привет, **{message.from_user.first_name}**!\n\n"
        f"Добро пожаловать в магазин MKch.\n\n"
        f"🔑 **{PRODUCT_TITLE}**\n"
        f"💰 Цена: **{PRICE_STARS} ⭐ Stars**\n"
        f"📦 {stock_text}\n\n"
        f"Нажми кнопку ниже, чтобы приобрести пасскод:",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🛒 Купить пасскод", callback_data="buy_passcode"
                    )
                ],
                [InlineKeyboardButton("📦 Наличие", callback_data="check_stock")],
            ]
        ),
    )


@app.on_callback_query(filters.regex("^check_stock$"))
async def cb_stock(client: Client, cq):
    stock = count_passcodes()
    text = (
        f"📦 В наличии: **{stock} пасскодов**"
        if stock > 0
        else "😔 Пасскоды закончились!"
    )
    await cq.answer(text, show_alert=True)


@app.on_callback_query(filters.regex("^buy_passcode$"))
async def cb_buy(client: Client, callback_query):
    if count_passcodes() == 0:
        await callback_query.answer(
            "😔 Пасскоды закончились. Загляни позже!", show_alert=True
        )
        return
    await callback_query.answer()
    await client.send_invoice(
        chat_id=callback_query.message.chat.id,
        title=PRODUCT_TITLE,
        description=PRODUCT_DESCRIPTION,
        payload=PAYLOAD,
        currency="XTR",
        prices=[LabeledPrice(label=PRODUCT_TITLE, amount=PRICE_STARS)],
    )


@app.on_message(filters.command("buy") & filters.private)
async def cmd_buy(client: Client, message: Message):
    if count_passcodes() == 0:
        await message.reply("😔 Пасскоды закончились. Загляни позже!")
        return
    await client.send_invoice(
        chat_id=message.chat.id,
        title=PRODUCT_TITLE,
        description=PRODUCT_DESCRIPTION,
        payload=PAYLOAD,
        currency="XTR",
        prices=[LabeledPrice(label=PRODUCT_TITLE, amount=PRICE_STARS)],
    )


@app.on_pre_checkout_query()
async def pre_checkout(client: Client, query: PreCheckoutQuery):
    if query.invoice_payload != PAYLOAD:
        await query.answer(
            ok=False, error_message="Неверный товар. Попробуйте снова или позже."
        )
        return
    if count_passcodes() == 0:
        await query.answer(
            ok=False,
            error_message="К сожалению, пасскоды закончились. Оплата отменена.",
        )
        return
    await query.answer(ok=True)


@app.on_message(filters.successful_payment & filters.private)
async def on_payment(client: Client, message: Message):
    payment = message.successful_payment
    charge_id = payment.telegram_payment_charge_id
    if not register_processed_charge(processed_charge_ids, charge_id):
        log.warning("Дубликат события оплаты проигнорирован: charge_id=%s", charge_id)
        return

    log.info(
        "Успешная оплата от user_id=%d, Stars=%d, charge_id=%s",
        message.from_user.id,
        payment.total_amount,
        charge_id,
    )
    passcode = pop_passcode()
    if passcode is None:
        await message.reply(
            "⚠️ Что-то пошло не так: пасскоды закончились.\n"
            "Пожалуйста, напиши в поддержку — мы вернём Stars или выдадим пасскод вручную.\n\n"
            f"🧾 ID транзакции: `{charge_id}`"
        )
        log.error(
            "Пасскод не выдан! user_id=%d, charge_id=%s",
            message.from_user.id,
            charge_id,
        )
        return
    await message.reply(
        f"✅ Оплата прошла успешно!\n\n"
        f"🔑 Твой пасскод:\n"
        f"```\n{passcode}\n```\n\n"
        f"🧾 ID транзакции: `{charge_id}`\n\n"
        f"Сохрани его! 🛡"
    )


def admin_keyboard():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📦 Статистика", callback_data="adm_stats")],
            [
                InlineKeyboardButton(
                    "➕ Добавить администратора", callback_data="adm_add_admin"
                )
            ],
            [
                InlineKeyboardButton(
                    "📂 Загрузить пасскоды из файла", callback_data="adm_upload"
                )
            ],
        ]
    )


@app.on_message(filters.command("admin") & filters.private)
async def cmd_admin(client: Client, message: Message):
    if message.from_user.id not in get_admins():
        await message.reply("⛔ У тебя нет доступа к панели администратора.")
        return
    stock = count_passcodes()
    await message.reply(
        f"🛠 **Панель администратора**\n\n"
        f"📦 Пасскодов в наличии: **{stock} шт.**\n"
        f"👑 Главный админ: `{OWNER_ID}`\n"
        f"👥 Всего администраторов: **{len(get_admins())}**",
        reply_markup=admin_keyboard(),
    )


@app.on_callback_query(filters.regex("^adm_stats$"))
async def adm_stats(client: Client, cq):
    if cq.from_user.id not in get_admins():
        await cq.answer("⛔ Нет доступа", show_alert=True)
        return
    stock = count_passcodes()
    await cq.answer(
        f"📦 Пасскодов: {stock} шт.\n👥 Админов: {len(get_admins())}", show_alert=True
    )


@app.on_callback_query(filters.regex("^adm_add_admin$"))
async def adm_add_admin_start(client: Client, cq):
    if cq.from_user.id not in get_admins():
        await cq.answer("⛔ Нет доступа", show_alert=True)
        return
    pending_add_admin[cq.from_user.id] = True
    await cq.answer()
    await cq.message.reply(
        "👤 Введи Telegram ID пользователя, которого хочешь сделать администратором:\n\n"
        "(Узнать ID можно через @userinfobot)\n\n"
        "Для отмены — /cancel"
    )


@app.on_message(filters.command("cancel") & filters.private)
async def cmd_cancel(client: Client, message: Message):
    pending_add_admin.pop(message.from_user.id, None)
    pending_upload.pop(message.from_user.id, None)
    await message.reply("❌ Действие отменено.")


@app.on_message(
    filters.private
    & filters.text
    & ~filters.command(["start", "buy", "admin", "cancel"])
)
async def handle_text_input(client: Client, message: Message):
    uid = message.from_user.id
    if pending_add_admin.get(uid):
        pending_add_admin.pop(uid)
        text = message.text.strip()
        if not text.isdigit():
            await message.reply(
                "⚠️ Это не похоже на Telegram ID. Введи например: `987654321`"
            )
            return
        new_id = int(text)
        if new_id == uid:
            await message.reply("Нельзя добавить самого себя.")
            return
        if add_admin(new_id):
            await message.reply(f"✅ Администратор `{new_id}` успешно добавлен!")
            log.info("Новый админ: %d (добавил: %d)", new_id, uid)
        else:
            await message.reply(
                f"ℹ️ Пользователь `{new_id}` уже является администратором."
            )
        return
    if pending_upload.get(uid):
        await message.reply("📎 Пришли именно **.txt файл**, а не текст.")
        return


@app.on_callback_query(filters.regex("^adm_upload$"))
async def adm_upload_start(client: Client, cq):
    if cq.from_user.id not in get_admins():
        await cq.answer("⛔ Нет доступа", show_alert=True)
        return
    pending_upload[cq.from_user.id] = True
    await cq.answer()
    await cq.message.reply(
        "📂 Пришли **.txt файл** с пасскодами.\n"
        "Каждый пасскод — на отдельной строке.\n\n"
        "Дубликаты будут пропущены автоматически.\n"
        "Для отмены — /cancel"
    )


@app.on_message(filters.private & filters.document)
async def handle_document(client: Client, message: Message):
    uid = message.from_user.id
    if not pending_upload.get(uid):
        return
    if uid not in get_admins():
        await message.reply("⛔ Нет доступа.")
        return
    doc = message.document
    if not is_txt_filename(doc.file_name):
        await message.reply("⚠️ Пришли именно **.txt** файл.")
        return

    pending_upload.pop(uid)
    fd, tmp_path = tempfile.mkstemp(prefix=f"passcodes_upload_{uid}_", suffix=".txt")
    os.close(fd)
    try:
        await client.download_media(message, file_name=tmp_path)
        added, skipped = append_passcodes_from_file(tmp_path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    stock = count_passcodes()
    await message.reply(
        f"✅ Файл обработан!\n\n"
        f"➕ Добавлено: **{added} пасскодов**\n"
        f"⏭ Пропущено дубликатов: **{skipped}**\n"
        f"📦 Итого в наличии: **{stock} шт.**"
    )
    log.info(
        "Загрузка пасскодов: добавлено=%d, дублей=%d, загрузил user_id=%d",
        added,
        skipped,
        uid,
    )


if __name__ == "__main__":
    log.info("Бот запускается...")
    app.run()
