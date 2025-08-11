# -*- coding: utf-8 -*-
import asyncio
import datetime
import os
import sys
import time
import shutil
import base64
import subprocess
import logging
from urllib.parse import urljoin

import requests
import telegram
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)


class BotController:
    def __init__(self):
        self.telegram_token = os.environ.get("TELEGRAM_TOKEN")
        self.chat_id = os.environ.get("CHAT_ID")
        self.browserless_token = os.environ.get("BROWSERLESS_TOKEN")

        # --- CAMBIO: Usar conexión HTTP (CDP) que es más robusta en entornos de nube ---
        self.browserless_url = (
            f"https://chrome.browserless.io?token={self.browserless_token}"
        )

        self.INTERACTIVE_CAM_TIMEOUT = 240  # 4 minutos de timeout

        if not all([self.telegram_token, self.chat_id, self.browserless_token]):
            logging.error(
                "FATAL: Faltan variables de entorno (TELEGRAM_TOKEN, CHAT_ID, BROWSERLESS_TOKEN)."
            )
            sys.exit("Configuración incompleta. Saliendo.")

        self.cam_config = self._get_camera_config()
        self.metar_icaos = ["MROC", "MRPV", "MRLB"]
        self.satellite_maps = self._get_satellite_maps_config()
        self.WEBCAM_OUTPUT_FOLDER = "output_webcams"
        self.SATELLITE_OUTPUT_FOLDER = "output_satellite"

    def _get_camera_config(self):
        return [
            {
                "name": "Cartago",
                "page_url": "https://cartagoenvivo.com/",
                "base_url": "https://cartagoenvivo.com/",
                "image_id": "liveImage",
                "type": "image",
            },
            {
                "name": "Volcan Turrialba",
                "page_url": "https://www.ovsicori.una.ac.cr/index.php/vulcanologia/camara-volcanes-2/camara-v-turrialba",
                "base_url": "https://www.ovsicori.una.ac.cr",
                "image_id": "camara",
                "type": "interactive_simple",  # <-- CAMBIO
            },
            {
                "name": "Volcan Irazu",
                "page_url": "https://www.ovsicori.una.ac.cr/index.php/vulcanologia/camara-volcanes-2/camara-2-v-turrialba",
                "base_url": "https://www.ovsicori.una.ac.cr",
                "image_id": "camara",
                "type": "interactive_simple",  # <-- CAMBIO
            },
            {
                "name": "Poas Crater",
                "page_url": "https://www.ovsicori.una.ac.cr/index.php/vulcanologia/camara-volcanes-2/camara-crater-v-poas",
                "base_url": "https://www.ovsicori.una.ac.cr",
                "image_id": "camara",
                "type": "image",  # Esta usualmente funciona bien, la dejamos estática
            },
            {
                "name": "Poas SO del Crater",
                "page_url": "https://www.ovsicori.una.ac.cr/index.php/vulcanologia/camara-volcanes-2/camara-v-poas-so-del-crater",
                "base_url": "https://www.ovsicori.una.ac.cr",
                "image_id": "camara",
                "type": "interactive_simple",  # <-- CAMBIO
            },
            {
                "name": "Poas Chahuites",
                "page_url": "https://www.ovsicori.una.ac.cr/index.php/vulcanologia/camara-volcanes-2/camara-v-poas-chahuites",
                "base_url": "https://www.ovsicori.una.ac.cr",
                "image_id": "camara",
                "type": "image",  # Esta usualmente funciona bien, la dejamos estática
            },
            {
                "name": "Rincon de la Vieja Sensoria",
                "page_url": "https://www.ovsicori.una.ac.cr/index.php/vulcanologia/camara-volcanes-2/rincon-de-la-vieja-sensoria2",
                "base_url": "https://www.ovsicori.una.ac.cr",
                "image_id": "camara",
                "type": "interactive_simple",  # <-- CAMBIO
            },
            {
                "name": "Rincon de la Vieja Curubande",
                "page_url": "https://www.ovsicori.una.ac.cr/index.php/vulcanologia/camara-volcanes-2/camara-v-rincon-de-la-vieja-curubande",
                "base_url": "https://www.ovsicori.una.ac.cr",
                "image_id": "camara",
                "type": "image",
            },
            {
                "name": "Rincon de la Vieja Gavilan",
                "page_url": "https://www.ovsicori.una.ac.cr/index.php/vulcanologia/camara-volcanes-2/rincon-de-la-vieja-gavilan",
                "base_url": "https://www.ovsicori.una.ac.cr",
                "image_id": "camara",
                "type": "image",
            },
            {
                "name": "Reserva Karen Mogensen",
                "page_url": "https://www.forestepersempre.org/fps/progetti/CostaRica/webcam/Karen-webcam.html",
                "base_url": "https://www.forestepersempre.org",
                "image_id": "webcam",
                "type": "image",
            },
            {
                "name": "Cobano Skyline",
                "page_url": "https://www.skylinewebcams.com/webcam/costa-rica/puntarenas/puntarenas/cobano.html?w=4652",
                "type": "interactive",
            },
        ]

    def _get_satellite_maps_config(self):
        return {
            "start_url": "https://rammb.cira.colostate.edu/ramsdis/online/rmtc.asp#Central_and_South_America",
            "maps": [
                {
                    "id": "rmtc/rmtccosvis1",
                    "caption": "Animación Satelital (Visible) - Costa Rica",
                },
                {
                    "id": "rmtc/rmtccosvis2",
                    "caption": "Animación Satelital (Infrarrojo) - Costa Rica",
                },
                {
                    "id": "rmtc/rmtccosir22",
                    "caption": "Animación Satelital (Infrarrojo Onda Corta) - CR",
                },
                {
                    "id": "rmtc/rmtccosir42",
                    "caption": "Animación Satelital (Vapor de Agua) - CR",
                },
            ],
        }

    def get_static_webcam_image(self, camera_config):
        cam_name = camera_config["name"]
        try:
            logging.info(f"📡 Procesando cámara estática: {cam_name}")
            response = requests.get(camera_config["page_url"], timeout=20)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            img_tag = soup.find("img", {"id": camera_config["image_id"]})
            if not img_tag or not img_tag.get("src"):
                logging.warning(f"No se encontró el tag de imagen para '{cam_name}'.")
                return None
            abs_url = urljoin(camera_config["base_url"], img_tag["src"])
            img_response = requests.get(abs_url, timeout=20)
            img_response.raise_for_status()
            if img_response.content:
                filename = f"{cam_name.replace(' ', '_').lower()}.jpg"
                path = os.path.join(self.WEBCAM_OUTPUT_FOLDER, filename)
                with open(path, "wb") as f:
                    f.write(img_response.content)
                logging.info(f"Imagen '{cam_name}' guardada.")
                return (path, cam_name)
            logging.warning(f"Imagen '{cam_name}' descargada pero vacía.")
        except Exception as e:
            logging.error(f"Error con la cámara '{cam_name}': {e}", exc_info=True)
        return None

    # --- NUEVA FUNCIÓN para cámaras dinámicas simples (OVSICORI) ---
    async def get_simple_interactive_image(self, camera_config):
        cam_name = camera_config["name"]
        logging.info(f"📸 Procesando cámara dinámica simple con Playwright: {cam_name}")
        async with async_playwright() as p:
            browser = None
            try:
                browser = await p.chromium.connect_over_cdp(
                    self.browserless_url, timeout=120000
                )
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
                )
                page = await context.new_page()
                await page.goto(
                    camera_config["page_url"],
                    wait_until="domcontentloaded",
                    timeout=60000,
                )

                image_selector = f"img#{camera_config['image_id']}"
                await page.wait_for_selector(
                    image_selector, state="visible", timeout=30000
                )

                element = page.locator(image_selector)

                filename = f"{cam_name.replace(' ', '_').lower()}.png"
                path = os.path.join(self.WEBCAM_OUTPUT_FOLDER, filename)

                await element.screenshot(path=path)

                logging.info(f"Captura simple '{cam_name}' guardada.")
                return (path, cam_name)
            except Exception as e:
                logging.error(
                    f"Error con la cámara dinámica simple '{cam_name}': {e}",
                    exc_info=True,
                )
                return None
            finally:
                if browser:
                    await browser.close()

    async def get_interactive_webcam_image(self, camera_config):
        cam_name = camera_config["name"]
        logging.info(f"🤖 Procesando cámara interactiva con Playwright: {cam_name}")
        async with async_playwright() as p:
            browser = None
            try:
                # --- CAMBIO: Usar connect_over_cdp y aumentar timeout ---
                browser = await p.chromium.connect_over_cdp(
                    self.browserless_url, timeout=120000
                )
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
                    viewport={"width": 1920, "height": 1080},
                )
                page = await context.new_page()

                await page.goto(
                    camera_config["page_url"], wait_until="networkidle", timeout=60000
                )
                await page.wait_for_selector(".play-wrapper", timeout=25000)
                await page.evaluate('document.querySelector(".play-wrapper").click()')
                await asyncio.sleep(30)
                await page.wait_for_selector("button[data-fullscreen]", timeout=10000)
                await page.click("button[data-fullscreen]")
                await asyncio.sleep(3)

                filename = f"{cam_name.replace(' ', '_').lower()}.png"
                path = os.path.join(self.WEBCAM_OUTPUT_FOLDER, filename)
                await page.screenshot(path=path, full_page=True)

                logging.info(f"Captura interactiva '{cam_name}' guardada.")
                return (path, cam_name)
            except Exception as e:
                logging.error(
                    f"Error con la cámara interactiva '{cam_name}': {e}", exc_info=True
                )
                return None
            finally:
                if browser:
                    await browser.close()

    # --- FUNCIÓN ACTUALIZADA para procesar todas las cámaras en paralelo ---
    async def get_all_webcam_images(self):
        logging.info("Iniciando descarga de imágenes de webcams.")
        image_data = []

        tasks = []
        for camera in self.cam_config:
            try:
                if camera.get("type") == "interactive":
                    tasks.append(
                        asyncio.wait_for(
                            self.get_interactive_webcam_image(camera),
                            timeout=self.INTERACTIVE_CAM_TIMEOUT,
                        )
                    )
                elif camera.get("type") == "interactive_simple":
                    tasks.append(
                        asyncio.wait_for(
                            self.get_simple_interactive_image(camera),
                            timeout=self.INTERACTIVE_CAM_TIMEOUT,
                        )
                    )
                else:
                    tasks.append(
                        asyncio.to_thread(self.get_static_webcam_image, camera)
                    )
            except Exception as e:
                logging.error(f"Error al crear tarea para {camera['name']}: {e}")

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, res in enumerate(results):
            if i < len(self.cam_config):
                cam_name = self.cam_config[i]["name"]
                if isinstance(res, Exception):
                    logging.error(f"Falló la tarea para la cámara '{cam_name}': {res}")
                elif res:
                    image_data.append(res)

        return image_data

    async def generate_and_send_satellite_videos(self, bot):
        logging.info("Iniciando generación de videos satelitales con Playwright.")
        async with async_playwright() as p:
            browser = None
            try:
                # --- CAMBIO: Usar connect_over_cdp y aumentar timeout ---
                browser = await p.chromium.connect_over_cdp(
                    self.browserless_url, timeout=120000
                )
                context = await browser.new_context()
                page = await context.new_page()

                config = self.satellite_maps
                for i, mapa in enumerate(config["maps"]):
                    map_id, map_caption = mapa["id"], mapa["caption"]
                    logging.info(
                        f"Procesando Mapa Satelital {i + 1}/{len(config['maps'])}: {map_caption}"
                    )

                    await page.goto(
                        config["start_url"], wait_until="load", timeout=90000
                    )
                    await page.click(f'a[href*="data_folder={map_id}"]')
                    await page.wait_for_selector(
                        "#downloadLoop", state="visible", timeout=90000
                    )
                    await asyncio.sleep(5)
                    await page.evaluate(
                        'document.querySelector("#downloadLoop").click()'
                    )
                    img_locator = page.locator("#animatedGifWrapper img")
                    await img_locator.wait_for(state="visible", timeout=120000)
                    data_url = await img_locator.get_attribute("src")

                    _, encoded_data = data_url.split(",", 1)
                    gif_path = os.path.join(self.SATELLITE_OUTPUT_FOLDER, "temp.gif")
                    with open(gif_path, "wb") as f:
                        f.write(base64.b64decode(encoded_data))

                    mp4_path = os.path.join(self.SATELLITE_OUTPUT_FOLDER, "video.mp4")
                    if self.convert_gif_to_mp4(gif_path, mp4_path):
                        await self.send_video_to_telegram(bot, mp4_path, map_caption)
                    else:
                        logging.error(
                            "Envío omitido por error en la conversión de GIF a MP4."
                        )
            except Exception as e:
                logging.error(f"Error en el proceso satelital: {e}", exc_info=True)
            finally:
                if browser:
                    await browser.close()

    def get_metar_reports(self):
        logging.info("Obteniendo reportes METAR.")
        api_url = f"https://aviationweather.gov/api/data/metar?ids={','.join(self.metar_icaos)}&format=json"
        report_text = (
            f"*{'Reporte Meteorológico de Aeropuertos'}*\n_{datetime.datetime.now(datetime.timezone.utc).astimezone(datetime.timezone(datetime.timedelta(hours=-6))).strftime('%Y-%m-%d %I:%M %p %Z')}_\n"
            + ("-" * 30)
            + "\n\n"
        )
        nombres = {
            "MROC": "Juan Santamaría",
            "MRPV": "Tobías Bolaños",
            "MRLB": "Daniel Oduber",
        }
        try:
            data = requests.get(api_url, timeout=20).json()
            for reporte in data:
                icao, metar = (
                    reporte.get("icaoId", "N/A"),
                    reporte.get("rawOb", "No disponible"),
                )
                nombre = nombres.get(icao, "")
                report_text += f"*{icao} ({nombre})*:\n`{metar}`\n\n"
            logging.info("Reportes METAR obtenidos con éxito.")
        except Exception as e:
            logging.error(f"Error obteniendo datos METAR: {e}", exc_info=True)
            report_text += "No se pudieron obtener los datos meteorológicos."
        return report_text

    def convert_gif_to_mp4(self, gif_path, mp4_path):
        logging.info(f"Convirtiendo {os.path.basename(gif_path)} a MP4...")
        try:
            command = [
                "ffmpeg",
                "-i",
                gif_path,
                "-movflags",
                "faststart",
                "-pix_fmt",
                "yuv420p",
                "-vf",
                "scale=trunc(iw/2)*2:trunc(ih/2)*2",
                "-y",
                mp4_path,
            ]
            subprocess.run(
                command,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            logging.info("Conversión a MP4 completada.")
            return True
        except FileNotFoundError:
            logging.error("FATAL: FFmpeg no está instalado en el entorno de ejecución.")
            return False
        except Exception as e:
            logging.error(f"Error en la conversión con FFmpeg: {e}", exc_info=True)
            return False

    async def send_report_to_telegram(self, bot, text_message, image_data):
        logging.info("Enviando reporte principal a Telegram.")
        try:
            await bot.send_message(
                chat_id=self.chat_id, text=text_message, parse_mode="Markdown"
            )
            logging.info("Mensaje de texto (METAR) enviado.")

            media_group = [
                telegram.InputMediaPhoto(open(path, "rb"), caption=name)
                for path, name in image_data
                if os.path.exists(path) and os.path.getsize(path) > 0
            ]
            if media_group:
                for i in range(0, len(media_group), 10):
                    chunk = media_group[i : i + 10]
                    await bot.send_media_group(
                        chat_id=self.chat_id,
                        media=chunk,
                        read_timeout=60,
                        write_timeout=60,
                    )
                    logging.info(f"Grupo de {len(chunk)} imágenes enviado.")
                    await asyncio.sleep(1)
            else:
                logging.warning("No hay imágenes válidas para enviar.")
        except Exception as e:
            logging.error(f"Error al enviar reporte a Telegram: {e}", exc_info=True)

    async def send_video_to_telegram(self, bot, video_path, caption):
        logging.info(f"Enviando video '{os.path.basename(video_path)}' a Telegram.")
        try:
            with open(video_path, "rb") as video_file:
                await bot.send_video(
                    chat_id=self.chat_id,
                    video=video_file,
                    caption=caption,
                    supports_streaming=True,
                    read_timeout=60,
                    write_timeout=60,
                )
            logging.info("Video enviado con éxito.")
        except Exception as e:
            logging.error(f"Error al enviar video a Telegram: {e}", exc_info=True)

    async def run(self):
        start_time = time.time()
        logging.info("================ INICIANDO EJECUCIÓN DEL BOT ================")
        for folder in [self.WEBCAM_OUTPUT_FOLDER, self.SATELLITE_OUTPUT_FOLDER]:
            if os.path.exists(folder):
                shutil.rmtree(folder)
            os.makedirs(folder)

        bot = telegram.Bot(token=self.telegram_token)

        metar_task = asyncio.to_thread(self.get_metar_reports)
        webcam_task = self.get_all_webcam_images()

        metar_report, image_data = await asyncio.gather(metar_task, webcam_task)

        await self.send_report_to_telegram(bot, metar_report, image_data)
        await self.generate_and_send_satellite_videos(bot)

        end_time = time.time()
        logging.info(f"🎉 PROCESO COMPLETADO en {end_time - start_time:.2f} segundos.")
        logging.info("================ EJECUCIÓN FINALIZADA ================")


if __name__ == "__main__":
    controller = BotController()
    asyncio.run(controller.run())
