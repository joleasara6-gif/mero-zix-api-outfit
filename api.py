from flask import Flask, request, jsonify, send_file
import requests
from PIL import Image
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor
import os

app = Flask(__name__)
main_key = "MERO&ZIX"
executor = ThreadPoolExecutor(max_workers=10)

# Lấy thông tin người chơi
def fetch_player_info(uid, region):
    url = f'https://nr-codex-info1.vercel.app/player-info?uid={uid}&region={region}'
    response = requests.get(url)
    return response.json() if response.status_code == 200 else None

# Tải và xử lý ảnh
def fetch_and_process_image(image_url, size=None):
    try:
        response = requests.get(image_url)
        if response.status_code == 200:
            image = Image.open(BytesIO(response.content)).convert("RGBA")
            if size:
                image = image.resize(size)
            return image
        return None
    except:
        return None

@app.route('/outfit-image', methods=['GET'])
def outfit_image():
    uid = request.args.get('uid')
    region = request.args.get('region')
    key = request.args.get('key')

    if not uid or not region:
        return jsonify({'error': 'Missing uid or region'}), 400
    if key != main_key:
        return jsonify({'error': 'Invalid or missing API key'}), 403

    data = fetch_player_info(uid, region)
    if not data:
        return jsonify({'error': 'Failed to fetch player info'}), 500

    # Lấy dữ liệu từ JSON mới
    clothes_ids = data.get("AccountProfileInfo", {}).get("EquippedOutfit", [])
    equipped_skills = data.get("AccountProfileInfo", {}).get("EquippedSkills", [])
    pet_id = data.get("petInfo", {}).get("id")
    weapon_ids = data.get("AccountInfo", {}).get("EquippedWeapon", [])
    weapon_id = weapon_ids[0] if weapon_ids else None

    # Tiền tố từng loại item + fallback mặc định
    required_starts = ["211", "214", "211", "203", "204", "205", "203"]
    fallback_ids = ["211000000", "214000000", "208000000", "203000000", "204000000", "205000000", "203000000"]
    used_ids = set()
    outfit_images = []

    # Tải icon từng phần trang phục
    def fetch_outfit_image(idx, code):
        matched = None
        for oid in clothes_ids:
            str_oid = str(oid)
            if str_oid.startswith(code) and oid not in used_ids:
                matched = oid
                used_ids.add(oid)
                break
        if matched is None:
            matched = fallback_ids[idx]
        url = f'https://www.dl.cdn.freefireofficial.com/icons/{matched}.png'
        return fetch_and_process_image(url, size=(170, 170))

    for idx, code in enumerate(required_starts):
        outfit_images.append(executor.submit(fetch_outfit_image, idx, code))

    # Nền
    bg_url = 'https://iili.io/KHeErOv.jpg'
    background_image = fetch_and_process_image(bg_url, size=(1024, 1024))
    if not background_image:
        return jsonify({'error': 'Failed to fetch background image'}), 500

    # Vị trí từng item trên ảnh
    positions = [
        {'x': 760,  'y': 92, 'width': 170, 'height': 170},  # Mũ
        {'x': 810,  'y': 310, 'width': 170, 'height': 120},  # Mặt
        {'x': 790,  'y': 490, 'width': 170, 'height': 170},  # Phụ kiện đầu phải (trùng code mũ/mặt)
        {'x': 72,   'y': 505, 'width': 170, 'height': 170},  # Áo
        {'x': 130,   'y': 792, 'width': 170, 'height': 170},  # Quần
        {'x': 728,  'y': 760, 'width': 170, 'height': 170},  # Giày
        {'x': 72,  'y': 230 , 'width': 170, 'height': 170},  
    ] # 174 752 50 575

    # Dán từng trang phục lên nền
    for idx, future in enumerate(outfit_images):
        outfit_image = future.result()
        if outfit_image:
            pos = positions[idx]
            resized = outfit_image.resize((pos['width'], pos['height']))
            background_image.paste(resized, (pos['x'], pos['y']), resized)

    # Dán pet nếu có
    if pet_id:
        pet_url = f'https://www.dl.cdn.freefireofficial.com/icons/{pet_id}.pg'
        pet_image = fetch_and_process_image(pet_url, size=(140, 170))
        if pet_image:
            background_image.paste(pet_image, (700, 700), pet_image)

    # Dán Avatar nếu có kỹ năng kết thúc bằng "06"
    avatar_id = next((s for s in equipped_skills if str(s).endswith("06")), 406)
    avatar_url = f'https://characteriroxmar.vercel.app/chars?id={avatar_id}'
    avatar_image = fetch_and_process_image(avatar_url, size=(650, 780))
    if avatar_image:
        center_x = (1024 - avatar_image.width) // 2
        background_image.paste(avatar_image, (center_x, 145), avatar_image)

    # Dán vũ khí
    if weapon_id:
        weapon_url = f'https://www.dl.cdn.freefireofficial.com/icons/{weapon_id}.pg'
        weapon_image = fetch_and_process_image(weapon_url, size=(330, 200))
        if weapon_image:
            background_image.paste(weapon_image, (670, 564), weapon_image)

    # Xuất ảnh PNG
    img_io = BytesIO()
    background_image.save(img_io, 'PNG')
    img_io.seek(0)
    return send_file(img_io, mimetype='image/png')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
