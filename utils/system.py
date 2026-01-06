import logging
import subprocess


def check_system_dependencies():
    """Проверяем системные зависимости"""
    logging.info("=== ПРОВЕРКА СИСТЕМНЫХ ЗАВИСИМОСТЕЙ ===")

    # Проверяем FFmpeg
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            logging.info("✅ FFmpeg найден")
            # Получаем версию из вывода
            version_line = result.stdout.split('\n')[0]
            logging.info(f"   Версия: {version_line}")
        else:
            logging.error("❌ FFmpeg не работает корректно")
            return False
    except FileNotFoundError:
        logging.error("❌ FFmpeg не найден в PATH")

        # Пробуем найти альтернативные пути
        possible_paths = [
            "/usr/bin/ffmpeg",
            "/usr/local/bin/ffmpeg",
            "/bin/ffmpeg",
            "ffmpeg"
        ]

        for path in possible_paths:
            try:
                subprocess.run([path, "-version"],
                               capture_output=True,
                               text=True)
                logging.info(f"✅ FFmpeg найден по пути: {path}")
                return True
            except (FileNotFoundError, PermissionError, OSError) as e:
                logging.error(f"❌ FFmpeg не найден по пути {path}: {type(e).__name__}")
                continue
            except Exception as e:
                logging.error(f"Неожиданная ошибка при проверке {path}: {e}")
                continue

        return False

    # Проверяем другие команды
    commands_to_check = ["which", "ls", "mkdir", "rm"]
    for cmd in commands_to_check:
        try:
            subprocess.run([cmd, "--version"],
                           capture_output=True,
                           text=True)
            logging.debug(f"✅ {cmd} доступен")
        except FileNotFoundError:
            logging.error(f"❌ {cmd} не найден в системе")
        except PermissionError:
            logging.error(f"🔒 {cmd} найден, но нет прав на выполнение")
        except subprocess.TimeoutExpired:
            logging.error(f"⏰ Проверка {cmd} превысила таймаут")
        except OSError as e:
            logging.error(f"💥 Ошибка ОС при проверке {cmd}: {e}")
        except Exception as e:
            logging.error(f"🚨 Неожиданная ошибка при проверке {cmd}: {e}", exc_info=True)

    logging.info("=== ПРОВЕРКА ЗАВЕРШЕНА ===")
    return True