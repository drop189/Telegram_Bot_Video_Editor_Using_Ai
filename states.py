from aiogram.fsm.state import StatesGroup, State


# ============ ADMIN СОСТОЯНИЯ ============
class AdminSendMessage(StatesGroup):
    waiting_for_user_choice = State()
    waiting_for_message_text = State()


# ============ FSM СОСТОЯНИЯ ============
class VideoProcessing(StatesGroup):
    waiting_for_theme = State()
    waiting_for_video = State()
    processing = State()
