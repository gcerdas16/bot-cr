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
from pyppeteer import connect

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
        self.browserless_url = (
            f"wss://chrome.browserless.io?token={self.browserless_token}"
        )
        # --- CAMBIO 1: Se añade la variable de timeout ---
        self.INTERACTIVE_CAM_TIMEOUT = 180  # Timeout en segundos (3 minutos)

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
                "type": "image",
            },
            {
                "name": "Volcan Irazu",
                "page_url": "https://www.ovsicori.una.ac.cr/index.php/vulcanologia/camara-volcanes-2/camara-2-v-turrialba",
                "base_url": "https://www.ovsicori.una.ac.cr",
                "image_id": "camara",
                "type": "image",
            },
            {
                "name": "Poas Crater",
                "page_url": "https://www.ovsicori.una.ac.cr/index.php/vulcanologia/camara-volcanes-2/camara-crater-v-poas",
                "base_url": "https://www.ovsicori.una.ac.cr",
                "image_id": "camara",
                "type": "image",
            },
            {
                "name": "Poas SO del Crater",
                "page_url": "https://www.ovsicori.una.ac.cr/index.php/vulcanologia/camara-volcanes-2/camara-v-poas-so-del-crater",
                "base_url": "https://www.ovsicori.una.ac.cr",
                "image_id": "camara",
                "type": "image",
            },
            {
                "name": "Poas Chahuites",
                "page_url": "https://www.ovsicori.una.ac.cr/index.php/vulcanologia/camara-volcanes-2/camara-v-poas-chahuites",
                "base_url": "https://www.ovsicori.una.ac.cr",
                "image_id": "camara",
                "type": "image",
            },
            {
                "name": "Rincon de la Vieja Sensoria",
                "page_url": "https://www.ovsicori.una.ac.cr/index.php/vulcanologia/camara-volcanes-2/rincon-de-la-vieja-sensoria2",
                "base_url": "https://www.ovsicori.una.ac.cr",
                "image_id": "camara",
                "type": "image",
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

    async def get_interactive_webcam_image(self, camera_config):
        cam_name = camera_config["name"]
        logging.info(f"🤖 Procesando cámara interactiva: {cam_name}")
        browser = None
        try:
            browser = await connect(browserWSEndpoint=self.browserless_url)
            page = await browser.newPage()
            await page.setViewport({"width": 1920, "height": 1080})
            await page.goto(
                camera_config["page_url"],
                {"waitUntil": "networkidle2", "timeout": 60000},
            )
            await page.waitForSelector(".play-wrapper", {"timeout": 25000})
            await page.click(".play-wrapper")
            await asyncio.sleep(30)
            await page.waitForSelector("button[data-fullscreen]", {"timeout": 10000})
            await page.click("button[data-fullscreen]")
            await asyncio.sleep(3)
            filename = f"{cam_name.replace(' ', '_').lower()}.png"
            path = os.path.join(self.WEBCAM_OUTPUT_FOLDER, filename)
            await page.screenshot({"path": path, "fullPage": True})
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

    async def get_all_webcam_images(self):
        logging.info("Iniciando descarga de imágenes de webcams.")
        image_data = []
        for camera in self.cam_config:
            result = None
            if camera.get("type") == "interactive":
                try:
                    # --- CAMBIO 2: Se usa la nueva variable para el timeout ---
                    result = await asyncio.wait_for(
                        self.get_interactive_webcam_image(camera),
                        timeout=self.INTERACTIVE_CAM_TIMEOUT,
                    )
                except asyncio.TimeoutError:
                    logging.error(f"Timeout en captura de '{camera['name']}'.")
            else:
                result = self.get_static_webcam_image(camera)
            if result:
                image_data.append(result)
            await asyncio.sleep(1)
        return image_data

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

    async def generate_and_send_satellite_videos(self, bot):
        logging.info("Iniciando generación de videos satelitales.")
        browser = None
        try:
            browser = await connect(browserWSEndpoint=self.browserless_url)
            page = await browser.newPage()
            config = self.satellite_maps
            for i, mapa in enumerate(config["maps"]):
                map_id, map_caption = mapa["id"], mapa["caption"]
                logging.info(
                    f"Procesando Mapa Satelital {i + 1}/{len(config['maps'])}: {map_caption}"
                )
                await page.goto(
                    config["start_url"], {"waitUntil": "networkidle2", "timeout": 90000}
                )
                await page.waitForSelector(f'a[href*="data_folder={map_id}"]')
                await page.click(f'a[href*="data_folder={map_id}"]')
                await page.waitForSelector(
                    "#downloadLoop", {"visible": True, "timeout": 90000}
                )
                await asyncio.sleep(5)
                await page.evaluate('document.querySelector("#downloadLoop").click()')
                await page.waitForFunction(
                    "() => { const img = document.querySelector('#animatedGifWrapper img'); return img && img.src.startsWith('data:image'); }",
                    {"timeout": 120000},
                )
                data_url = await page.evaluate(
                    "document.querySelector('#animatedGifWrapper img').src"
                )
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
