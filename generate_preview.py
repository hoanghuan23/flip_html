"""Nhận kịch bản từ analyze_text.py để phân tích, sinh ảnh và dựng HTML động.

python3 generate_preview.py --script kich_ban.md --plan-only
python3 generate_preview.py --resume --phase 1
python3 generate_preview.py --resume
"""

import argparse
import base64
import binascii
import copy
import hashlib
import html
import io
import json
import math
import os
from pathlib import Path
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from analyze_text import ROOT, request_text

PLAN_PROMPT = """
Bạn chuyển KỊCH BẢN ĐÃ CÓ thành kế hoạch ảnh tĩnh + HTML sprite animation.
Chỉ trả một JSON object hợp lệ, không Markdown. Không viết lại kịch bản.
Giữ đúng số phase, thứ tự sự kiện, thời lượng từng phase và tổng thời lượng.
Chưa dùng HyperFrames, không tạo video, MP4 hay âm thanh.

Schema (thay toàn bộ dữ liệu ví dụ bằng nội dung kịch bản):
{
  "title": "Tên câu chuyện",
  "style": "Mô tả phong cách, palette và thiết kế cố định của TẤT CẢ nhân vật/vật thể",
  "total_duration": 4,
  "assets": [
    {"id":"street", "kind":"backgrounds", "size":"1536x1024",
     "columns":1, "rows":1, "poses":["background"],
     "prompt":"Ảnh nền không có nhân vật/vật thể đã được tách thành sprite"},
    {"id":"girl", "kind":"characters", "size":"1536x1024",
     "columns":3, "rows":1, "poses":["stand","walk_1","walk_2"],
     "prompt":"Thiết kế cố định. Mô tả cụ thể từng tư thế theo thứ tự các ô"}
  ],
  "phases": [
    {"title":"Tên phase", "duration":4, "background":"street",
     "start_state":"Trạng thái đầu", "end_state":"Trạng thái cuối",
     "events":[{"start":0,"end":4,"description":"Hành động trong kịch bản"}],
     "rain":[{"time":0,"value":1},{"time":4,"value":1}],
     "rainbow":[{"time":0,"value":0},{"time":4,"value":0}],
     "tracks":[
       {"id":"girl", "asset":"girl", "width":18, "z":10,
        "keyframes":[
          {"time":0,"x":20,"y":85,"pose":["walk_1","walk_2"],"fps":6},
          {"time":3,"x":55,"y":85,"pose":"stand"},
          {"time":4,"x":55,"y":85,"pose":"stand"}
        ]}
     ]}
  ]
}

Ràng buộc:
- ID chỉ có chữ thường ASCII, số, dấu gạch dưới; ID bắt đầu bằng chữ.
- Chỉ liệt kê ảnh THỰC SỰ cần, tối đa 32 assets. Nền riêng; mỗi nhân vật một
  sprite sheet PNG trong suốt gồm đủ tư thế cho tất cả phase, tối đa 16 ô/sheet.
  Vật thể có thể là sheet riêng (ô đóng/mở). Không vẽ ô vào sprite cô bé nếu ô là asset riêng.
- Giữ ngoại hình/áo quần/kích thước trong mọi pose. Cùng asset ID được tái sử dụng.
- poses theo thứ tự ô từ trái sang phải, trên xuống dưới; columns*rows >= số poses.
  Kiểm đếm số poses trước khi chọn lưới: ví dụ 13 poses cần lưới 4x4, không phải 4x3.
  Từng ô bằng nhau; sprite cùng tỷ lệ, bàn chân/điểm neo ở giữa sát đáy mỗi ô.
  size là WIDTHxHEIGHT, các kích thước chia hết cho columns/rows tương ứng.
- tracks dùng tọa độ phần trăm stage 16:9: x từ trái, y từ trên, neo ở chân/đáy
  sprite. width là % chiều rộng stage; z là thứ tự lớp. X có thể ngoài 0–100 khi ra/vào cảnh.
  Tỷ lệ sprite được giữ theo kích thước ô ảnh, không có trường height.
- Mỗi keyframe có time,x,y,pose. time tính bằng giây TRONG phase, tăng nghiêm ngặt,
  bắt đầu 0 và kết thúc đúng duration. Nội suy tuyến tính x,y,opacity,rotation,scale.
  Mặc định opacity=1, rotation=0, scale=1, flip=false. Ghi rõ nếu khác mặc định.
  pose là một tên hoặc mảng tên chạy theo fps (mặc định 6), đổi rời rạc tại keyframe.
  Keyframe cuối dùng một pose cố định. Khi đi dùng >=2 frame chân khác nhau;
  cúi/nhặt/mở/khép/nhìn lên cần tư thế khác, không chỉ trượt sprite đứng yên.
- Mỗi asset sprite có anchor:[0.5,0.94] (tọa độ chuẩn hóa trong frame, chân/đáy).
  Có thể thêm sockets:{"hand":{"stand":[0.65,0.5],"walk_1":[0.66,0.52],...}};
  socket phải có điểm riêng cho TẤT CẢ poses, khớp tay thật trong ảnh.
  Có thể dùng track.sockets để hiệu chỉnh vị trí socket trên PNG đã sinh mà không sinh lại ảnh.
- Vật được cầm PHẢI dùng attach ở từng keyframe khi cầm:
  "attach":{"track":"girl","socket":"hand","anchor":[0.5,0.8],"offset":[0,0]}.
  anchor trong attach là điểm cầm trên FRAME VẬT THỂ; offset là đơn vị frame cha.
  attach:null khi vật còn đặt trên đất. x,y vẫn ghi để giữ schema nhưng chỉ dùng
  khi không attach. Vật gắn theo vị trí socket, rotation/scale/flip/opacity của cha.
  Khi đổi pose vật có thể đổi attach.anchor cho đúng vị trí tay cầm trong frame đó.
  Không tạo chu trình attach. Không dùng scene_bound cho vật cầm. Điểm nhặt/giơ/khép
  và thời điểm đổi pose phải khớp nhau. Giữ attach liên tục giữa hai phase.
- Nhân vật ngồi trên phương tiện cũng PHẢI dùng attach: track cha là phương tiện,
  socket là điểm yên/ghế theo từng pose; attach.anchor là điểm hông ngồi trên frame
  nhân vật. Không đặt chung điểm chân/đáy của người và xe lên cùng x,y.
  Chọn tỷ lệ người/xe để hông chạm yên, tay chạm ghi-đông và chân đặt trên gác chân.
  Khi xe máy chạy, giữ tư thế ngồi; không luân phiên chân như đạp xe đạp.
  Tháo attach tại lúc nhân vật rời ghế/ngã. Không tạo chu trình cha/con.
- Đo kích thước NỘI DUNG nhìn thấy trong frame, kể cả lề trong suốt: đèn giao thông
  phải cao hợp lý so với người và xe, bánh xe nằm trên mặt đường thực tế của ảnh nền.
  Nếu xe không giảm tốc thì các đoạn đường có cùng vận tốc; khi yêu cầu đi hết khung,
  keyframe cuối phải đưa TOÀN BỘ xe và người ra ngoài, không chỉ vượt vạch dừng.
- Giữ cùng track ID và asset giữa các phase; trong cùng shot giữ width, z.
  Trong cùng shot, keyframe đầu phase sau phải có cùng x,y,pose,opacity,rotation,scale,flip
  với keyframe cuối phase trước. Chỉ được đặt lại x/y khi track đã ra HẾT ngoài khung
  ở cuối phase trước và background thay đổi, hoặc khai báo camera cut trong staging.
  Qua camera cut phải chiếu lại tọa độ và tỷ lệ, vẫn giữ pose và attachment. Nhân vật còn thấy ở
  cuối phase phải tiếp tục có track ở phase sau. Track chưa xuất hiện có thể opacity=0.
- Track đồ vật gắn cố định với bối cảnh (cửa nhà, bàn, bồn cây) phải có
  "scene_bound":true. Chỉ dùng cho asset kind="objects"; không dùng cho nhân vật
  hay vật được mang theo như ô cầm tay. Track scene_bound được phép không xuất hiện
  ở phase kế tiếp nếu background thay đổi. Khi background giữ nguyên, vẫn phải
  giữ track nếu còn hiện. Mặc định scene_bound=false và phải giữ giá trị giữa các phase.
- rain/rainbow là đường cong cường độ 0–1 với mốc từ 0 đến duration; không có hiệu ứng
  thì cả hai mốc value=0. Dùng rain/rainbow để dựng mưa/cầu vồng bằng CSS theo thời gian.
- events ghi các hành động thực tế để người xem đối chiếu khi tua.
- Dàn cảnh TRƯỚC khi viết prompt nền: xác định tọa độ chân, lối đi, vị trí bồn cây,
  mái hiên và hướng đến đích. Ghi các tọa độ % stage đó ngay trong prompt nền;
  nền và keyframes phải dùng cùng mặt đất/phối cảnh. Chừa lối đi ngang liên tục.
  Nhân vật đi vào cảnh bắt đầu ngoài biên, không xuất hiện sẵn giữa đường.
  Nhân vật đã đứng chờ dưới mái hiên phải ở đúng dưới mái hiên từ đầu cảnh;
  mốc kể chuyện giới thiệu nhân vật không có nghĩa là fade-in hay xuất hiện đột ngột.
  Mèo co ro phải đặt sát chân bồn cây, không đặt giữa đường.
- Khi đi chung về một hướng, người đứng chờ bước XUÔI theo hướng đó để nhập nhóm;
  người cầm ô tiến đến đón, không kéo người đứng chờ trượt lùi vào ô.
  Mỗi đoạn có dịch chuyển dùng chu kỳ >=2 pose bước chân; dừng lại dùng pose tĩnh.
  Đặt mảng pose trên keyframe ĐẦU đoạn đang đi, không chỉ trên keyframe đích.
  Không giữ pose mời/chỉ tay suốt đoạn còn đổi x/y. Xen tư thế chân khép giữa hai
  bước chân dang nếu sheet có sẵn, để nhịp bước nhìn rõ thay vì hai ảnh gần giống nhau.
  Xếp nhóm để cô bé ở giữa, mèo và bạn nhỏ hai bên, không chồng kín các sprite.
- Ô phải che được nhóm nhưng để thấy rõ mặt. Chọn socket tay cầm và attach.anchor
  theo PNG thực tế, kiểm tra cả pose cúi/che mèo/mời bạn; không dùng tọa độ tay đưa
  ra mời làm tay giữ ô. Tán ô nên nằm phía sau lớp nhân vật để không che khuôn mặt.
- Cảnh bước ra khỏi nhà: nhân vật ở trong nhà, ẩn khi cửa đóng; cửa mở trước khi
  nhân vật xuất hiện ở ngưỡng cửa rồi bước xuống thềm. Không đặt sẵn nhân vật ngoài cửa.
  Vật nằm trên đất cần rotation và vị trí neo đúng mặt đất, giữ yên đến lúc nhặt.
  Khi kịch bản yêu cầu đi hết khung hình, cả nhân vật và vật cầm phải ra ngoài biên
  trước duration; không kết thúc đường đi ở giữa cảnh.
- start_state/end_state mô tả tính liên tục. Toàn bộ prompt ảnh dùng cùng style.

HỢP ĐỒNG DÀN CẢNH (bắt buộc cho plan mới, trước khi sinh ảnh):
- Mỗi phase có staging:{"shot":"street_side","view":"side","transition":"cut",
  "pixels_per_meter":110,"ground":{"road":[[0,78],[100,78],[100,100],[0,100]]},
  "focus":[50,60],"camera":[{"time":0,"zoom":1},{"time":4,"zoom":1}]}.
  ground là các đa giác vùng tiếp đất dự kiến, tọa độ % stage; sau sinh ảnh phải đo lại.
  view chỉ là side, three_quarter hoặc overhead. transition là cut hoặc continuous.
- Mỗi track có geometry:{"reference_pose":"stand","axis":"height","size_m":1.75,
  "role":"adult","ground":"road","baked_poses":[],"views":["side"],"motion":"free"}.
  axis width/height đo phần HÌNH THẬT trong PNG, không đo cả ô trong suốt.
  size_m là chiều dài/cao THẬT của reference_pose; mọi track trong cùng shot dùng
  chung pixels_per_meter. Người lớn đứng cao khoảng 1.6–1.9 m, sedan dài 4–5 m,
  xe máy dài 1.8–2.3 m. Người ngồi phải dùng chiều cao ngồi của đúng reference_pose.
  role là adult, sedan, motorcycle, signal hoặc other; dùng đúng loại để kiểm tra kích thước.
  Bỏ ground cho vật cầm hoặc sprite đang bay; ground phải là tên vùng trong staging.
  views là góc nhìn sprite thực sự cần vẽ. Không ghép sprite ngang với nền overhead.
- baked_poses liệt kê pose đã vẽ nghiêng/ngã/nằm; rotation của các pose đó phải bằng 0,
  tránh xoay hai lần. Dùng pose PNG cho động tác ngã, không xoay ảnh nằm thêm -30/-55 độ.
- Nếu chuyển camera: khai báo shot mới + transition cut, tính lại TẤT CẢ tọa độ,
  tỷ lệ và thứ tự lớp theo shot mới; giữ asset, diễn biến, pose và vật đang cầm.
  Không bắt tọa độ màn hình/tỷ lệ giống hệt qua hai camera khác nhau.
- Nếu continuous: giữ shot, nền, view, pixels_per_meter, ground và focus;
  camera đầu nối camera cuối. Cảnh hỗ trợ sau tai nạn giữ nguyên nền hiện trường.
  Camera lùi bằng đường cong zoom của staging, tác động lên CẢ nền và mọi sprite;
  không sinh nền phố khác rồi giữ nguyên x/y. zoom >= 1 để không hở biên.
- geometry.motion constant kiểm tra vận tốc các đoạn bằng nhau; thêm exit:right/left
  chỉ khi kịch bản yêu cầu ra hết khung. Hệ thống sẽ kiểm tra theo ảnh sau hiệu chỉnh.
- geometry.forward là right/left theo hướng gốc nhân vật/xe trong PNG;
  locomotion_poses liệt kê các pose đi/chạy (ví dụ walk_1, walk_2). Khi di chuyển
  phải flip đúng hướng; không để người đi sang trái nhưng chân/mặt bước sang phải.
- Không xếp mọi người cùng một điểm. Dành khoảng trống riêng cho xe, nạn nhân,
  người hỗ trợ và lối tiếp cận. Không đặt hiện trường lên vỉa hè chỉ để vừa tọa độ.
- Các thông số trên là dự kiến, CHƯA phải chứng nhận hình ảnh đã đúng. Sau sinh PNG,
  chương trình đo alpha, tính lại kích thước và kiểm tra mặt đất, tốc độ, ra khỏi khung.

KỊCH BẢN ĐÃ CÓ:
"""


def number(value, label, low=-10000, high=10000):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or not low <= value <= high):
        raise ValueError(f"{label}: cần số hữu hạn trong [{low}, {high}].")
    return value


def text_value(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label}: cần chuỗi không rỗng.")
    return value


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", value):
        raise ValueError(f"ID không hợp lệ: {value!r}.")
    return value


def objects(value, label):
    if not isinstance(value, list) or not value or not all(isinstance(v, dict) for v in value):
        raise ValueError(f"{label}: cần danh sách object không rỗng.")
    return value


def asset_path(asset):
    return f"assets/{asset['kind']}/{asset['id']}.png"


def point(value, label, low=0, high=1):
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{label}: cần [x,y].")
    return [number(v, label, low, high) for v in value]


def validate_plan(plan):
    """Kiểm tra trước khi tốn request sinh ảnh; không thực thi mã do AI trả về."""
    if not isinstance(plan, dict):
        raise ValueError("Kế hoạch phải là JSON object.")
    for key in ("title", "style"):
        text_value(plan.get(key), key)
    assets = objects(plan.get("assets"), "assets")
    if len(assets) > 32:
        raise ValueError("Chỉ tạo tối đa 32 tài nguyên.")
    by_id = {}
    for asset in assets:
        aid = identifier(asset.get("id"))
        if aid in by_id or asset.get("kind") not in ("backgrounds", "characters", "objects"):
            raise ValueError(f"Asset trùng ID hoặc sai kind: {aid}.")
        text_value(asset.get("prompt"), f"{aid}.prompt")
        size = re.fullmatch(r"([1-9][0-9]{1,3})x([1-9][0-9]{1,3})", str(asset.get("size")))
        if not size:
            raise ValueError(f"{aid}: size phải dạng WIDTHxHEIGHT, mỗi chiều tối đa 8192.")
        width, height = map(int, size.groups())
        cols, rows = asset.get("columns"), asset.get("rows")
        for key, value in (("columns", cols), ("rows", rows)):
            if type(value) is not int or not 1 <= value <= 16:
                raise ValueError(f"{aid}.{key}: cần số nguyên 1–16.")
        poses = asset.get("poses")
        if (width > 8192 or height > 8192 or width % cols or height % rows
                or cols * rows > 16 or not isinstance(poses, list) or not poses
                or len(poses) > cols * rows or any(not isinstance(p, str) for p in poses)
                or len(set(poses)) != len(poses)):
            raise ValueError(f"{aid}: kích thước/lưới/poses không hợp lệ.")
        for pose in poses:
            identifier(pose)
        if asset["kind"] == "backgrounds" and (cols != 1 or rows != 1):
            raise ValueError(f"{aid}: nền phải là một ảnh, không phải sprite sheet.")
        if asset["kind"] == "backgrounds" and len(poses) != 1:
            raise ValueError(f"{aid}: nền phải có đúng một frame.")
        asset["anchor"] = point(asset.get("anchor", [0.5, 0.94]), f"{aid}.anchor")
        if (asset["kind"] != "backgrounds"
                and not (0.05 <= asset["anchor"][0] <= 0.95 and 0.1 <= asset["anchor"][1] <= 0.98)):
            raise ValueError(f"{aid}.anchor: cần chừa lề để đặt trọn sprite trong frame.")
        sockets = asset.setdefault("sockets", {})
        if not isinstance(sockets, dict):
            raise ValueError(f"{aid}.sockets: cần object.")
        for name, positions in sockets.items():
            identifier(name)
            if not isinstance(positions, dict) or set(positions) != set(poses):
                raise ValueError(f"{aid}.{name}: socket cần điểm cho tất cả poses.")
            for pose, position in positions.items():
                point(position, f"{aid}.{name}.{pose}")
        by_id[aid] = asset
    phases = objects(plan.get("phases"), "phases")
    total = 0
    for index, phase in enumerate(phases, 1):
        label = f"phase_{index}"
        for key in ("title", "start_state", "end_state"):
            text_value(phase.get(key), f"{label}.{key}")
        duration = number(phase.get("duration"), f"{label}.duration", 0.1, 600)
        total += duration
        background = identifier(phase.get("background"))
        if by_id.get(background, {}).get("kind") != "backgrounds":
            raise ValueError(f"{label}: không tìm thấy ảnh nền.")
        for event in objects(phase.get("events"), f"{label}.events"):
            start = number(event.get("start"), "event.start", 0, duration)
            number(event.get("end"), "event.end", start, duration)
            text_value(event.get("description"), "event.description")
        for effect in ("rain", "rainbow"):
            curve = objects(phase.get(effect), effect)
            check_times(curve, duration, effect)
            for sample in curve:
                number(sample.get("value"), effect, 0, 1)
        track_ids = set()
        for track in objects(phase.get("tracks"), f"{label}.tracks"):
            tid = identifier(track.get("id"))
            aid = identifier(track.get("asset"))
            if tid in track_ids or aid not in by_id or by_id[aid]["kind"] == "backgrounds":
                raise ValueError(f"{label}: track {tid} trùng ID hoặc sai asset.")
            track_ids.add(tid)
            scene_bound = track.get("scene_bound", False)
            if (not isinstance(scene_bound, bool)
                    or (scene_bound and by_id[aid]["kind"] != "objects")):
                raise ValueError(f"{tid}.scene_bound: cần boolean, chỉ bật cho đồ vật gắn với bối cảnh.")
            track["scene_bound"] = scene_bound
            sockets = track.setdefault("sockets", {})
            if not isinstance(sockets, dict):
                raise ValueError(f"{tid}.sockets: cần object.")
            for name, positions in sockets.items():
                identifier(name)
                if not isinstance(positions, dict) or set(positions) != set(by_id[aid]["poses"]):
                    raise ValueError(f"{tid}.{name}: socket cần điểm cho tất cả poses.")
                for pose, position in positions.items():
                    point(position, f"{tid}.{name}.{pose}")
            number(track.get("width"), f"{tid}.width", 0.1, 150)
            layout = track.setdefault("layout", {})
            if not isinstance(layout, dict) or any(k not in ("width", "offset") for k in layout):
                raise ValueError(f"{tid}.layout: chỉ nhận width và offset.")
            if "width" in layout:
                number(layout["width"], f"{tid}.layout.width", 0.1, 150)
            if "offset" in layout:
                point(layout["offset"], f"{tid}.layout.offset", -100, 100)
            if type(track.get("z")) is not int or not 0 <= track["z"] <= 1000:
                raise ValueError(f"{tid}.z: cần số nguyên trong [0, 1000].")
            frames = objects(track.get("keyframes"), f"{tid}.keyframes")
            check_times(frames, duration, tid)
            for frame in frames:
                for key in ("x", "y"):
                    number(frame.get(key), f"{tid}.{key}", -300, 400)
                for key, default, lo, hi in (("opacity", 1, 0, 1), ("scale", 1, 0.01, 10),
                                            ("rotation", 0, -720, 720), ("fps", 6, 0.1, 60)):
                    frame[key] = number(frame.get(key, default), f"{tid}.{key}", lo, hi)
                frame.setdefault("flip", False)
                if not isinstance(frame["flip"], bool):
                    raise ValueError(f"{tid}.flip phải là boolean.")
                poses = frame.get("pose")
                if isinstance(poses, str):
                    poses = [poses]
                if (not isinstance(poses, list) or not poses
                        or any(p not in by_id[aid]["poses"] for p in poses)):
                    raise ValueError(f"{tid}: pose không tồn tại trong asset {aid}.")
            if not isinstance(frames[-1]["pose"], str):
                raise ValueError(f"{tid}: keyframe cuối cần một pose cố định.")
        check_attachments(phase, by_id)
        check_staging(phase, by_id, label)
        if index > 1:
            check_continuity(phases[index - 2], phase, label, by_id)
    number(plan.get("total_duration"), "total_duration", 0.1, 86400)
    if not math.isclose(total, plan["total_duration"], abs_tol=0.01):
        raise ValueError("Tổng thời lượng không bằng tổng các phase.")
    return plan


def check_attachments(phase, assets):
    tracks = {t["id"]: t for t in phase["tracks"]}
    edges = {tid: set() for tid in tracks}
    for tid, track in tracks.items():
        for frame in track["keyframes"]:
            attachment = frame.setdefault("attach", None)
            if attachment is None:
                continue
            if (not isinstance(attachment, dict) or attachment.get("track") not in tracks
                    or track["scene_bound"]):
                raise ValueError(f"{tid}.attach: cần track cha hợp lệ cho sprite gắn socket.")
            parent = tracks[attachment["track"]]
            sockets = {**assets[parent["asset"]]["sockets"], **parent["sockets"]}
            if attachment.get("socket") not in sockets:
                raise ValueError(f"{tid}.attach: socket không tồn tại.")
            attachment["anchor"] = point(attachment.get("anchor", assets[track["asset"]]["anchor"]),
                                         f"{tid}.attach.anchor")
            attachment["offset"] = point(attachment.get("offset", [0, 0]), f"{tid}.attach.offset", -2, 2)
            edges[tid].add(parent["id"])
    def visit(tid, trail):
        if tid in trail:
            raise ValueError(f"{tid}.attach: chu trình track cha/con.")
        for parent in edges[tid]:
            visit(parent, trail | {tid})
    for tid in tracks:
        visit(tid, set())


def check_times(points, duration, label):
    times = [number(p.get("time"), f"{label}.time", 0, duration) for p in points]
    if (len(times) < 2 or times[0] != 0 or times[-1] != duration
            or any(a >= b for a, b in zip(times, times[1:]))):
        raise ValueError(f"{label}: mốc thời gian phải tăng, từ 0 đến {duration}.")


def check_staging(phase, assets, label):
    """Optional for legacy plans; mandatory for newly analysed scripts."""
    staging = phase.get("staging")
    if staging is None:
        return
    if not isinstance(staging, dict):
        raise ValueError(f"{label}.staging: cần object.")
    identifier(staging.get("shot"))
    if staging.get("view") not in ("side", "three_quarter", "overhead"):
        raise ValueError(f"{label}.staging.view: sai góc nhìn.")
    if staging.get("transition") not in ("continuous", "cut"):
        raise ValueError(f"{label}.staging.transition: cần cut hoặc continuous.")
    number(staging.get("pixels_per_meter"), "pixels_per_meter", 1, 1000)
    ground = staging.get("ground")
    if not isinstance(ground, dict) or not ground:
        raise ValueError(f"{label}.ground: cần vùng tiếp đất.")
    for name, polygon in ground.items():
        identifier(name)
        validate_polygon(polygon, f"{label}.ground.{name}")
    staging["focus"] = point(staging.get("focus", [50, 50]), "camera.focus", 0, 100)
    camera = objects(staging.get("camera"), "camera")
    check_times(camera, phase["duration"], "camera")
    for frame in camera:
        number(frame.get("zoom"), "camera.zoom", 1, 3)
    for track in phase["tracks"]:
        aid = assets[track["asset"]]
        geometry = track.get("geometry")
        if not isinstance(geometry, dict):
            raise ValueError(f"{label}.{track['id']}: thiếu geometry.")
        if geometry.get("reference_pose") not in aid["poses"] or geometry.get("axis") not in ("width", "height"):
            raise ValueError(f"{track['id']}.geometry: reference_pose/axis sai.")
        number(geometry.get("size_m"), "geometry.size_m", 0.01, 100)
        role = geometry.get("role", "other")
        bounds = {"adult": {"height":(.5, 2.2), "width":(.5, 2.2)},
                  "sedan": {"height":(1.1, 2.1), "width":(3.5, 5.5)},
                  "motorcycle": {"height":(.8, 1.7), "width":(1.6, 2.6)},
                  "signal": {"height":(1.5, 5.5), "width":(.1, 1.5)}, "other": {}}
        if role not in bounds:
            raise ValueError(f"{track['id']}.geometry.role: loại vật thể không hợp lệ.")
        if geometry["axis"] in bounds[role]:
            lo, hi = bounds[role][geometry["axis"]]
            number(geometry["size_m"], f"{track['id']}: kích thước {role} theo mét", lo, hi)
        if geometry.get("ground") is not None and geometry["ground"] not in ground:
            raise ValueError(f"{track['id']}.geometry.ground: không có vùng này.")
        views = geometry.get("views")
        if not isinstance(views, list) or staging["view"] not in views:
            raise ValueError(f"{track['id']}: góc sprite không khớp góc camera {staging['view']}.")
        baked = geometry.get("baked_poses", [])
        if not isinstance(baked, list) or any(p not in aid["poses"] for p in baked):
            raise ValueError(f"{track['id']}.baked_poses: pose không tồn tại.")
        if geometry.get("motion", "free") not in ("constant", "free"):
            raise ValueError(f"{track['id']}.motion: cần constant/free.")
        if geometry.get("exit") not in (None, "left", "right"):
            raise ValueError(f"{track['id']}.exit: cần left/right.")
        locomotion = geometry.get("locomotion_poses", [])
        if (not isinstance(locomotion, list) or any(p not in aid["poses"] for p in locomotion)
                or (locomotion and geometry.get("forward") not in ("left", "right"))):
            raise ValueError(f"{track['id']}: locomotion_poses/forward không hợp lệ.")
        for a, b in zip(track["keyframes"], track["keyframes"][1:]):
            poses = [a["pose"]] if isinstance(a["pose"], str) else a["pose"]
            dx = b["x"]-a["x"]
            if not a["attach"] and abs(dx) > 1e-6 and any(p in locomotion for p in poses):
                direction = (1 if geometry["forward"] == "right" else -1)*(-1 if a["flip"] else 1)
                if dx*direction < 0:
                    raise ValueError(f"{track['id']}: hướng bước/ngồi lái ngược đường đi, cần sửa flip.")
        for frame in track["keyframes"]:
            poses = [frame["pose"]] if isinstance(frame["pose"], str) else frame["pose"]
            if any(p in baked for p in poses) and abs(frame["rotation"]) > 0.01:
                raise ValueError(f"{track['id']}: pose đã vẽ nghiêng/ngã, không xoay thêm rotation.")
        if geometry.get("motion") == "constant" and not any(f.get("attach") for f in track["keyframes"]):
            velocities = [((b["x"]-a["x"])*16/(b["time"]-a["time"]),
                           (b["y"]-a["y"])*9/(b["time"]-a["time"]))
                          for a, b in zip(track["keyframes"], track["keyframes"][1:])]
            if any(abs(v[i]-velocities[0][i]) > 0.01 for v in velocities for i in (0, 1)):
                raise ValueError(f"{track['id']}: chuyển động constant nhưng vận tốc các đoạn khác nhau.")


def validate_polygon(polygon, label):
    if not isinstance(polygon, list) or len(polygon) < 3:
        raise ValueError(f"{label}: đa giác cần ít nhất 3 điểm.")
    for vertex in polygon:
        point(vertex, label, 0, 100)
    area = sum(a[0]*b[1]-b[0]*a[1] for a, b in zip(polygon, polygon[1:]+polygon[:1]))
    if abs(area) < 0.01:
        raise ValueError(f"{label}: vùng tiếp đất rỗng.")


def endpoint_outside_stage(phase, assets, tid):
    """Conservatively require the whole transformed frame to leave horizontally."""
    tracks = {t["id"]: t for t in phase["tracks"]}
    states = {}

    def world_point(state, point):
        x, y, angle, sx, sy = state
        dx, dy = point[0] * sx, point[1] * sy
        return (x + dx * math.cos(angle) - dy * math.sin(angle),
                y + dx * math.sin(angle) + dy * math.cos(angle))

    def state_for(track_id):
        if track_id in states:
            return states[track_id]
        track = tracks[track_id]
        asset = assets[track["asset"]]
        frame = track["keyframes"][-1]
        layout = track.get("layout", {})
        width = layout.get("width", track["width"]) * 16
        sheet_width, sheet_height = dimensions(asset["size"])
        height = width * (sheet_height / asset["rows"]) / (sheet_width / asset["columns"])
        offset = layout.get("offset", [0, 0])
        anchor = asset["anchor"]
        angle = math.radians(frame["rotation"])
        sx = frame["scale"] * (-1 if frame["flip"] else 1)
        sy = frame["scale"]
        # Transform basis vectors as well as the position, including attachments.
        origin = ((frame["x"] + offset[0]) * 16, (frame["y"] + offset[1]) * 9)
        local = (*origin, angle, sx, sy)
        transform = lambda p: world_point(local, p)
        if frame["attach"]:
            binding = frame["attach"]
            parent_transform, parent_width, parent_height, parent_anchor = state_for(binding["track"])
            parent = tracks[binding["track"]]
            parent_asset = assets[parent["asset"]]
            sockets = {**parent_asset["sockets"], **parent["sockets"]}
            socket = sockets[binding["socket"]][parent["keyframes"][-1]["pose"]]
            grip = [(socket[i] - parent_anchor[i] + binding["offset"][i]) * size
                    for i, size in enumerate((parent_width, parent_height))]
            anchor = binding["anchor"]
            transform = lambda p: parent_transform(tuple(
                grip[i] + world_point((0, 0, angle, sx, sy), p)[i] for i in (0, 1)))
        states[track_id] = (transform, width, height, anchor)
        return states[track_id]

    transform, width, height, anchor = state_for(tid)
    xs = [transform(((x - anchor[0]) * width, (y - anchor[1]) * height))[0]
          for x in (0, 1) for y in (0, 1)]
    return max(xs) <= 0 or min(xs) >= 1600


def check_continuity(previous, current, label, assets):
    old_stage, new_stage = previous.get("staging"), current.get("staging")
    cut = bool(old_stage and new_stage and new_stage["transition"] == "cut"
               and old_stage["shot"] != new_stage["shot"])
    if old_stage and new_stage and not cut:
        if any(old_stage[k] != new_stage[k] for k in
               ("shot", "view", "pixels_per_meter", "ground", "focus")) or previous["background"] != current["background"]:
            raise ValueError(f"{label}: camera liên tục phải giữ nền và hệ tọa độ shot; đổi camera cần cut.")
        if old_stage["camera"][-1]["zoom"] != new_stage["camera"][0]["zoom"]:
            raise ValueError(f"{label}: zoom đầu không nối zoom cuối cảnh trước.")
    current_tracks = {t["id"]: t for t in current["tracks"]}
    for old in previous["tracks"]:
        end = old["keyframes"][-1]
        new = current_tracks.get(old["id"])
        visible = end["opacity"] > 0 and not endpoint_outside_stage(previous, assets, old["id"])
        if new is None:
            left_scene = (old.get("scene_bound", False)
                          and previous["background"] != current["background"])
            if visible and not left_scene:
                raise ValueError(f"{label}: track {old['id']} đang hiện rồi tự biến mất.")
            continue
        start = new["keyframes"][0]
        start_pose = start["pose"][0] if isinstance(start["pose"], list) else start["pose"]
        if (old["asset"] != new["asset"]
                or old.get("scene_bound", False) != new.get("scene_bound", False)
                or old.get("sockets", {}) != new.get("sockets", {})
                or (not cut and (any(old[k] != new[k] for k in ("width", "z"))
                                  or old.get("layout", {}) != new.get("layout", {})))):
            raise ValueError(f"{label}: thiết kế/kích thước/lớp của {old['id']} không liên tục.")
        if end["opacity"] == start["opacity"] == 0:
            continue
        # A completed exit may re-enter in a different shot. Keep the carried
        # object, pose and appearance continuous while allowing a new position.
        reposition = cut or (previous["background"] != current["background"]
                      and endpoint_outside_stage(previous, assets, old["id"]))
        continuous_values = ("opacity",) if cut else ("opacity", "scale", "rotation") if reposition else (
            "x", "y", "opacity", "scale", "rotation")
        if (start_pose != end["pose"] or (not cut and start["flip"] != end["flip"])
                or start.get("attach") != end.get("attach")
                or any(not math.isclose(end[k], start[k], abs_tol=0.001)
                       for k in continuous_values)):
            raise ValueError(f"{label}: trạng thái đầu {old['id']} khác cuối phase trước.")


def analyze_script(screenplay, output, ask=None):
    """Nhận chính text kịch bản, không sinh lại kịch bản trong bước này."""
    ask = ask or request_text
    prompt = PLAN_PROMPT + screenplay
    for attempt in range(1, 3):
        raw = ask(prompt)
        (output / f"plan_attempt_{attempt}.txt").write_text(raw, encoding="utf-8")
        try:
            clean = re.sub(r"^```(?:json)?\s*\n?|\n?```$", "", raw.strip())
            plan = validate_plan(json.loads(clean))
            if any("staging" not in phase for phase in plan["phases"]):
                raise ValueError("Plan mới phải có staging và geometry cho mọi phase/track.")
            return plan
        except (ValueError, TypeError, KeyError) as error:
            if attempt == 2:
                raise ValueError(f"Kế hoạch AI chưa hợp lệ: {error}. Xem plan_attempt_2.txt.") from error
            prompt = (PLAN_PROMPT + screenplay + "\n\nJSON trước bị lỗi: " + str(error)
                      + "\nSửa JSON dưới đây, giữ nguyên kịch bản. Chỉ trả JSON đầy đủ:\n" + raw)
    raise AssertionError("unreachable")


# Contract read from ../codex_server/server.py, GenerateRequest and /generate-image.
PIPELINE_VERSION = "codex-cli-png-sheet-v2"
ALPHA_NOISE_FLOOR = 8
VISUAL_LIMIT = ("Chỉ đạt kiểm tra kỹ thuật. Chưa xác minh ngoại hình, tỷ lệ cơ thể, đúng pose, "
                "tay/socket, nền không lẫn sprite hoặc độ nhất quán mỹ thuật; cần xem ảnh và tua Phase 1.")


def image_config(require_credentials=True):
    config = {
        "base_url": os.getenv("IMAGE_API_BASE_URL", "").strip().rstrip("/"),
        "model": os.getenv("IMAGE_MODEL", "").strip(),
        "quality": os.getenv("IMAGE_QUALITY", "medium").strip(),
        "background_size": os.getenv("IMAGE_BACKGROUND_SIZE", "1536x1024").strip(),
        "contract": "codex-server-generate-image-v1",
    }
    missing = [name for name, value in (("IMAGE_API_BASE_URL", config["base_url"]),
                                       ("IMAGE_MODEL", config["model"])) if not value]
    if require_credentials and not os.getenv("IMAGE_API_KEY", "").strip():
        missing.append("IMAGE_API_KEY")
    if missing:
        raise ValueError("Chưa cấu hình API sinh ảnh PNG: thiếu " + ", ".join(missing)
                         + ". Cần endpoint /generate-image của codex_server; không chuyển về SVG.")
    parsed = urlsplit(config["base_url"])
    if (parsed.scheme not in ("http", "https") or not parsed.netloc
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or not parsed.path.endswith("/generate-image")):
        raise ValueError("IMAGE_API_BASE_URL cần URL đầy đủ đến /generate-image của codex_server, "
                         "ví dụ http://127.0.0.1:8000/generate-image.")
    # This is the Codex CLI model, passed unchanged; the server selects the image tool internally.
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]*", config["model"]):
        raise ValueError("IMAGE_MODEL không hợp lệ theo schema GenerateRequest của codex_server.")
    if config["quality"] not in ("low", "medium", "high", "auto"):
        raise ValueError("IMAGE_QUALITY cần low, medium, high hoặc auto (chỉ là hướng dẫn trong prompt).")
    if not re.fullmatch(r"[1-9][0-9]{1,3}x[1-9][0-9]{1,3}", config["background_size"]):
        raise ValueError("IMAGE_BACKGROUND_SIZE cần dạng WIDTHxHEIGHT.")
    if max(dimensions(config["background_size"])) > 8192:
        raise ValueError("IMAGE_BACKGROUND_SIZE: tối đa 8192 mỗi chiều.")
    return config

def pillow_image():
    try:
        from PIL import Image
    except ImportError as error:
        raise ValueError("Thiếu Pillow: cài python3 -m pip install -r requirements.txt.") from error
    return Image


def dimensions(size):
    return tuple(map(int, size.split("x")))


def read_png(data, size, transparent):
    Image = pillow_image()
    try:
        with Image.open(io.BytesIO(data)) as source:
            if source.format != "PNG" or getattr(source, "n_frames", 1) != 1:
                raise ValueError("API/file phải là PNG tĩnh, không phải SVG/JPEG/APNG.")
            if source.size != dimensions(size):
                raise ValueError(f"PNG cần kích thước {size}, nhận {source.width}x{source.height}.")
            source.verify()
        with Image.open(io.BytesIO(data)) as source:
            if transparent and "A" not in source.getbands():
                raise ValueError("Sprite PNG thiếu alpha channel.")
            image = source.convert("RGBA")
            image.load()
    except (OSError, SyntaxError, Image.DecompressionBombError) as error:
        raise ValueError("PNG hỏng hoặc không giải mã được.") from error
    alpha = image.getchannel("A")
    if transparent and (alpha.getextrema()[0] != 0 or alpha.getextrema()[1] == 0):
        raise ValueError("Sprite phải có pixel trong suốt thật và nội dung không rỗng.")
    if not transparent and alpha.getextrema()[0] != 255:
        raise ValueError("Ảnh nền phải kín và opaque.")
    return image


def frame_info(image, label):
    # Nearly invisible alpha=1 pixels can be generation noise, rather than clipped artwork.
    bounds = image.getchannel("A").point(lambda value: 255 if value >= ALPHA_NOISE_FLOOR else 0).getbbox()
    if bounds is None:
        raise ValueError(f"{label}: frame rỗng.")
    left, top, right, bottom = bounds
    if left == 0 or top == 0 or right == image.width or bottom == image.height:
        raise ValueError(f"{label}: nội dung chạm biên, có thể bị cắt; cần sinh lại pose.")
    return list(bounds)


def png_info(data, asset):
    transparent = asset["kind"] != "backgrounds"
    image = read_png(data, asset["size"], transparent)
    columns, rows = asset["columns"], asset["rows"]
    if image.width % columns or image.height % rows or len(asset["poses"]) > columns * rows:
        raise ValueError(f"{asset['id']}: lưới/frame không hợp lệ.")
    width, height = image.width // columns, image.height // rows
    frames = []
    for index in range(columns * rows):
        x, y = index % columns * width, index // columns * height
        cell = image.crop((x, y, x + width, y + height))
        if index >= len(asset["poses"]):
            if cell.getchannel("A").getbbox() is not None:
                raise ValueError(f"{asset['id']}: ô thừa phải trong suốt.")
            continue
        bounds = frame_info(cell, asset["poses"][index]) if transparent else [0, 0, width, height]
        anchor = asset.get("anchor", [0.5, 0.94])
        if transparent and (abs(bounds[3] - round(height * anchor[1])) > 1
                            or abs((bounds[0] + bounds[2]) / 2 - width * anchor[0]) > 1):
            raise ValueError(f"{asset['id']}: frame lệch điểm chân/đáy hoặc trục giữa.")
        frames.append({"pose": asset["poses"][index], "index": index, "bbox": bounds,
                       "sha256": hashlib.sha256(cell.tobytes()).hexdigest()})
    return {"size": [image.width, image.height], "frame_size": [width, height],
            "frame_count": len(frames), "columns": columns, "rows": rows,
            "alpha": transparent, "frames": frames}


def image_prompt(plan, asset):
    prompt = (f"Shared art direction and fixed designs:\n{plan['style']}\n\n{asset['prompt']}\n"
              "Generate raster PNG artwork. No text, labels, watermark, borders or grid. ")
    if asset["kind"] == "backgrounds":
        excluded = ", ".join(a["id"] for a in plan["assets"] if a["kind"] != "backgrounds")
        placements = [{"asset": t["asset"], "width_percent": t["width"],
                       "base_x_percent": t["keyframes"][0]["x"],
                       "base_y_percent": t["keyframes"][0]["y"]}
                      for phase in plan["phases"] if phase["background"] == asset["id"]
                      for t in phase["tracks"] if t.get("scene_bound")]
        return (prompt + "Background plate only, full opaque canvas. No characters or separately animated props. "
                f"Exclude all separated assets: {excluded}. Preserve the setting and camera composition. "
                f"Reserve empty matching apertures/space for scene-bound sprites at these 16:9 stage placements: {json.dumps(placements)}. "
                "Do not paint rain streaks, rainbow arcs or other animated weather overlays; "
                "the HTML timeline adds those effects separately. A wet ground and overcast lighting are allowed.")
    return sheet_prompt(plan, asset)

def sheet_prompt(plan, asset):
    layout = "; ".join(f"cell {i+1}: {pose}" for i, pose in enumerate(asset["poses"]))
    excluded = [a["id"] for a in plan["assets"] if a["id"] != asset["id"]]
    isolation = ""
    if asset["kind"] == "characters":
        isolation = (
            f"\nHIGHEST PRIORITY ISOLATION RULE: This sheet depicts ONLY the single subject {asset['id']}. "
            f"NEVER depict these other assets in ANY cell: {', '.join(excluded)}. "
            "Pose descriptions refer to story actions only. Holding, opening, folding or sharing props "
            "must be PANTOMIMED WITH EMPTY HANDS: draw the correct arms and hand gestures, "
            "but the held object is INVISIBLE, absent from every pixel. "
            "Inviting or sheltering another character is a SOLO gesture toward empty transparent space. "
            "Do not illustrate mini-scenes. Exactly one isolated subject in each cell, no companion, "
            "no pet, no umbrella or other handheld prop. No colored halo or leftover background pixels. "
            "Leave at least 8% entirely empty transparent padding around each pose within its own cell.")
    return (f"Shared fixed art direction: {plan['style']}\n{asset['prompt']}\n"
            f"Generate exactly one raster PNG sprite sheet, canvas {asset['size']} pixels. "
            f"Grid: {asset['columns']} equal columns by {asset['rows']} equal rows. "
            f"EXACT row-major pose order, left to right then top to bottom: {layout}. "
            "Each named pose must be physically drawn, not simulated by rotating or scaling a standing pose. "
            "All poses show the SAME subject, fixed identity, clothing, palette, lighting, camera, "
            "pixels per body unit; crouched poses stay proportionally shorter. "
            "Exactly one entire subject inside each used cell, at least 5% transparent margin on all sides. "
            "Feet/base centered near the bottom of each cell. No clipping or overlap between cells. "
            "Unused cells completely transparent. Real alpha transparency, no checkerboard or scenery. "
            "No text, numbers, grid lines, labels, watermark, cast shadows or separately animated props. "
            f"Sockets in final normalized frame coordinates: {json.dumps(asset.get('sockets', {}))}. "
            "Use the image generation tool; never output SVG or drawing code." + isolation)


def request_image(prompt, config, *, transparent):
    """Call codex_server's image route, never the text route or a direct OpenAI API."""
    # GenerateRequest forbids all additional fields. The CLI model is not an image model ID.
    payload = {"model": config["model"], "prompt": prompt +
               f"\nRendering detail preference: {config['quality']}. " +
               ("Real transparent PNG alpha is required." if transparent else
                f"Opaque PNG background, {config['background_size']} pixels, full canvas.")}
    request = Request(config["base_url"], data=json.dumps(payload).encode(),
                      headers={"x-api-key": os.environ["IMAGE_API_KEY"],
                               "Content-Type": "application/json"}, method="POST")
    try:
        # Server allows 600 seconds for a Codex CLI image request.
        with urlopen(request, timeout=660) as response:
            result = json.load(response)
    except HTTPError as error:
        raise ValueError(f"codex_server /generate-image trả HTTP {error.code}, model CLI {config['model']}. "
                         "Kiểm tra x-api-key, model CLI và công cụ image_generation trên server. "
                         "Không chuyển về SVG; chạy --resume để tiếp tục.") from error
    except (ValueError, UnicodeError) as error:
        raise ValueError("codex_server phải trả JSON success/output_format/data[0].b64_json.") from error
    try:
        if result["success"] is not True or result["output_format"] != "png" or len(result["data"]) != 1:
            raise ValueError("codex_server phải trả success=true, output_format=png và đúng một ảnh.")
        data = base64.b64decode(result["data"][0]["b64_json"], validate=True)
        if not data.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("codex_server trả dữ liệu không phải PNG.")
        return data
    except (KeyError, IndexError, TypeError, binascii.Error) as error:
        raise ValueError("codex_server không trả PNG base64 đúng schema /generate-image.") from error

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def asset_recipe(plan, asset, config):
    return {"pipeline": PIPELINE_VERSION, "config": config, "asset": asset,
            "prompt": image_prompt(plan, asset),
            "normalization": "shared-cell-scale-align-base", "format": "png"}

def metadata_path(target):
    # SVG previously used <id>.meta.json; keep both its file and metadata intact.
    return target.with_suffix(".png.meta.json")


def atomic_bytes(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def save_cached(target, data, fingerprint, info):
    atomic_bytes(target, data)
    atomic_bytes(metadata_path(target), (json.dumps({"pipeline": PIPELINE_VERSION,
                 "fingerprint": fingerprint, "sha256": hashlib.sha256(data).hexdigest(),
                 "technical": info, "visual_review": "required", "limitations": VISUAL_LIMIT},
                 ensure_ascii=False, indent=2) + "\n").encode())


def cached_asset(target, fingerprint, inspect):
    try:
        meta = json.loads(metadata_path(target).read_text(encoding="utf-8"))
        data = target.read_bytes()
        if (meta.get("pipeline") != PIPELINE_VERSION or meta.get("fingerprint") != fingerprint
                or meta.get("sha256") != hashlib.sha256(data).hexdigest()
                or meta.get("technical") != inspect(data)):
            return None
        return data
    except (OSError, ValueError, TypeError, AttributeError):
        return None


def load_asset(plan, asset, output, config):
    target = output / asset_path(asset)
    data = cached_asset(target, digest(asset_recipe(plan, asset, config)), lambda data: png_info(data, asset))
    if data is None:
        raise ValueError(f"{asset_path(asset)}: file/metadata PNG thiếu, hỏng hoặc khác cấu hình/prompt; "
                         "chạy --resume --phase 1 để sinh lại. Cache SVG cũ không được dùng.")
    return data


def normalize_pose(data, asset, config):
    Image = pillow_image()
    source = read_png(data, config["sprite_size"], True)
    source.putalpha(source.getchannel("A").point(lambda value: value if value >= ALPHA_NOISE_FLOOR else 0))
    frame_info(source, asset["id"])
    width, height = dimensions(asset["size"])
    width //= asset["columns"]
    height //= asset["rows"]
    anchor = asset.get("anchor", [0.5, 0.94])
    # One scale for every pose, never resize each pose by its individual bounding box.
    factor = min(width * 2 * min(anchor[0], 1 - anchor[0]) * .9 / source.width,
                 height * anchor[1] * .95 / source.height)
    if factor <= 0:
        raise ValueError(f"{asset['id']}: anchor không đủ chỗ đặt sprite.")
    resized = source.resize((max(1, round(source.width * factor)), max(1, round(source.height * factor))),
                            Image.Resampling.LANCZOS)
    left, top, right, bottom = frame_info(resized, asset["id"])
    x = round(width * anchor[0] - (left + right) / 2)
    y = round(height * anchor[1] - bottom)
    if x + left <= 0 or y + top <= 0 or x + right >= width or y + bottom >= height:
        raise ValueError(f"{asset['id']}: pose không vừa frame/anchor, không tự cắt ảnh.")
    frame = Image.new("RGBA", (width, height))
    frame.alpha_composite(resized, (x, y))
    return frame


def generated_png(data, transparent):
    """The CLI has no size API parameter. Inspect its actual raster before fitting it."""
    Image = pillow_image()
    try:
        with Image.open(io.BytesIO(data)) as source:
            if max(source.size) > 8192 or min(source.size) < 16:
                raise ValueError("PNG nguồn cần mỗi chiều trong 16–8192 pixel.")
            size = f"{source.width}x{source.height}"
    except (OSError, SyntaxError, Image.DecompressionBombError) as error:
        raise ValueError("Không đọc được PNG nguồn từ codex_server.") from error
    return read_png(data, size, transparent)


def raw_sheet_info(data, asset):
    image = generated_png(data, True)
    columns, rows = asset["columns"], asset["rows"]
    expected_width, expected_height = dimensions(asset["size"])
    if (image.width % columns or image.height % rows
            or not math.isclose(image.width / image.height, expected_width / expected_height, rel_tol=.02)):
        raise ValueError(f"{asset['id']}: PNG nguồn sai tỷ lệ/lưới {columns}x{rows}; "
                         "codex_server chưa có tham số size để bảo đảm lưới. Cần sinh lại ảnh.")
    width, height = image.width // columns, image.height // rows
    frames = []
    for index in range(columns * rows):
        x, y = index % columns * width, index // columns * height
        frame = image.crop((x, y, x + width, y + height))
        if index >= len(asset["poses"]):
            # Apply the same noise floor as used poses; the final sheet leaves
            # unused cells entirely transparent instead of copying this noise.
            if frame.getchannel("A").point(lambda value: 255 if value >= ALPHA_NOISE_FLOOR else 0).getbbox() is not None:
                raise ValueError(f"{asset['id']}: ô thừa không trong suốt.")
        else:
            frames.append({"pose": asset["poses"][index], "bbox": frame_info(frame, asset["poses"][index])})
    return {"size": list(image.size), "frame_size": [width, height], "frames": frames}


def generate_assets(plan, output, phases, resume=False):
    config = image_config()
    Image = pillow_image()
    needed = {p["background"] for p in phases} | {t["asset"] for p in phases for t in p["tracks"]}
    for asset in plan["assets"]:
        if asset["id"] not in needed:
            continue
        target = output / asset_path(asset)
        recipe = asset_recipe(plan, asset, config)
        fingerprint = digest(recipe)
        if resume and cached_asset(target, fingerprint, lambda data: png_info(data, asset)) is not None:
            print(f"  Dùng lại {asset_path(asset)}", flush=True)
            continue
        raw_target = target.parent / ".source" / target.name
        def inspect_raw(data):
            if asset["kind"] != "backgrounds":
                return raw_sheet_info(data, asset)
            return {"size": list(generated_png(data, False).size)}
        data = cached_asset(raw_target, fingerprint, inspect_raw) if resume else None
        if data is None:
            print(f"  Sinh {asset_path(asset)} qua codex_server…", flush=True)
            data = request_image(recipe["prompt"], config, transparent=asset["kind"] != "backgrounds")
            # Preserve the original response for inspection even if the grid or alpha is rejected.
            # It gets no valid metadata until the technical checks pass, so resume never trusts it.
            atomic_bytes(raw_target, data)
            save_cached(raw_target, data, fingerprint, inspect_raw(data))
        else:
            print(f"  Ghép lại từ PNG nguồn {asset['id']}", flush=True)
        if asset["kind"] == "backgrounds":
            from PIL import ImageOps
            source = generated_png(data, False)
            sheet = ImageOps.fit(source, dimensions(asset["size"]), method=Image.Resampling.LANCZOS)
        else:
            info = raw_sheet_info(data, asset)
            source = generated_png(data, True)
            width, height = info["frame_size"]
            sheet = Image.new("RGBA", dimensions(asset["size"]))
            # Every cell shares the same size and normalization factor; no per-pose enlargement.
            for index, pose in enumerate(asset["poses"]):
                x, y = index % asset["columns"] * width, index // asset["columns"] * height
                frame = source.crop((x, y, x + width, y + height))
                stream = io.BytesIO()
                frame.save(stream, format="PNG")
                frame = normalize_pose(stream.getvalue(), asset, {"sprite_size": f"{width}x{height}"})
                sheet.alpha_composite(frame, (index % asset["columns"] * frame.width,
                                               index // asset["columns"] * frame.height))
        stream = io.BytesIO()
        sheet.save(stream, format="PNG")
        data = stream.getvalue()
        save_cached(target, data, fingerprint, png_info(data, asset))
    print("  " + VISUAL_LIMIT, flush=True)
    print("  codex_server chưa nhận ảnh tham chiếu; mỗi nhân vật sinh cùng một sheet để giữ thiết kế. "
          "Model trong metadata là model CLI, không xác định model ảnh nội bộ.", flush=True)

def layout_state(phase, assets, tid, time, states=None, blend=True):
    """Same deterministic design-space transforms as actorState in the browser."""
    states = {} if states is None else states
    if tid in states:
        return states[tid]
    tracks = {t["id"]: t for t in phase["tracks"]}
    track = tracks[tid]
    asset = assets[track["asset"]]
    frames = track["keyframes"]
    index = max(i for i, f in enumerate(frames) if f["time"] <= time)
    a, b = frames[index], frames[min(index+1, len(frames)-1)]
    ratio = 0 if a is b else (time-a["time"])/(b["time"]-a["time"])
    mix = lambda x, y: x+(y-x)*ratio
    pose = a["pose"]
    if isinstance(pose, list):
        start = index
        while start > 0 and frames[start-1]["pose"] == pose and frames[start-1]["fps"] == a["fps"]:
            start -= 1
        pose = pose[int(math.floor((time-frames[start]["time"])*a["fps"]+1e-9)) % len(pose)]
    scale = mix(a["scale"], b["scale"])
    angle = math.radians(mix(a["rotation"], b["rotation"]))
    sx = -scale if a["flip"] else scale
    sw, sh = dimensions(asset["size"])
    width = track.get("layout", {}).get("width", track["width"])*16
    offset = track.get("layout", {}).get("offset", [0, 0])
    state = {"x": (mix(a["x"], b["x"])+offset[0])*16,
             "y": (mix(a["y"], b["y"])+offset[1])*9,
             "width": width, "height": width*(sh/asset["rows"])/(sw/asset["columns"]),
             "anchor": asset["anchor"], "pose": pose, "opacity": mix(a["opacity"], b["opacity"]),
             "matrix": [math.cos(angle)*sx, math.sin(angle)*sx, -math.sin(angle)*scale, math.cos(angle)*scale]}
    if a["attach"]:
        binding = a["attach"]
        parent = layout_state(phase, assets, binding["track"], time, states)
        parent_track = tracks[binding["track"]]
        sockets = {**assets[parent_track["asset"]]["sockets"], **parent_track["sockets"]}
        socket = sockets[binding["socket"]][parent["pose"]]
        same = b["attach"] and all(binding[k] == b["attach"][k] for k in ("track", "socket"))
        off = [mix(v, b["attach"]["offset"][i]) if same else v for i, v in enumerate(binding["offset"])]
        state["anchor"] = [mix(v, b["attach"]["anchor"][i]) if same else v for i, v in enumerate(binding["anchor"])]
        state["x"], state["y"] = layout_point(parent, socket[0]+off[0], socket[1]+off[1])
        p, q = parent["matrix"], state["matrix"]
        state["matrix"] = [p[0]*q[0]+p[2]*q[1], p[1]*q[0]+p[3]*q[1],
                           p[0]*q[2]+p[2]*q[3], p[1]*q[2]+p[3]*q[3]]
        state["opacity"] *= parent["opacity"]
    changed = bool(a["attach"]) != bool(b["attach"]) or (a["attach"] and b["attach"] and
               any(a["attach"][k] != b["attach"][k] for k in ("track", "socket")))
    if blend and a is not b and changed:
        start = layout_state(phase, assets, tid, a["time"], blend=False)
        end = layout_state(phase, assets, tid, b["time"], blend=False)
        for key in ("x", "y", "opacity"):
            state[key] = mix(start[key], end[key])
        for key in ("anchor", "matrix"):
            state[key] = [mix(x, y) for x, y in zip(start[key], end[key])]
    states[tid] = state
    return state


def layout_point(state, x, y):
    dx = (x-state["anchor"][0])*state["width"]
    dy = (y-state["anchor"][1])*state["height"]
    a, b, c, d = state["matrix"]
    return state["x"]+a*dx+c*dy, state["y"]+b*dx+d*dy


def inside_polygon(x, y, polygon):
    inside = False
    for a, b in zip(polygon, polygon[1:]+polygon[:1]):
        # Points on the polygon boundary count as on the ground.
        cross = (x-a[0])*(b[1]-a[1])-(y-a[1])*(b[0]-a[0])
        if abs(cross) < 1e-6 and min(a[0], b[0])-1e-6 <= x <= max(a[0], b[0])+1e-6 and min(a[1], b[1])-1e-6 <= y <= max(a[1], b[1])+1e-6:
            return True
        if (a[1] > y) != (b[1] > y) and x < (b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:
            inside = not inside
    return inside


def layout_snapshot(plan, phase, time, output, measurements):
    """Render a review still from the same sprites/transforms, without an API call."""
    Image = pillow_image()
    assets = {a["id"]: a for a in plan["assets"]}
    with Image.open(output/asset_path(assets[phase["background"]])) as image:
        canvas = image.convert("RGBA").resize((1600, 900), Image.Resampling.LANCZOS)
    states = {}
    for track in sorted(phase["tracks"], key=lambda t: t["z"]):
        state = layout_state(phase, assets, track["id"], time, states)
        if state["opacity"] <= 0:
            continue
        asset = assets[track["asset"]]
        info = measurements[asset["id"]]
        fw, fh = info["frame_size"]
        index = asset["poses"].index(state["pose"])
        with Image.open(output/asset_path(asset)) as sheet:
            frame = sheet.crop((index % asset["columns"]*fw, index//asset["columns"]*fh,
                                (index % asset["columns"]+1)*fw, (index//asset["columns"]+1)*fh)).convert("RGBA")
        m = state["matrix"]
        a, b, c, d = m[0]*state["width"]/fw, m[1]*state["width"]/fw, m[2]*state["height"]/fh, m[3]*state["height"]/fh
        tx, ty = layout_point(state, 0, 0)
        det = a*d-b*c
        if abs(det) < 1e-9:
            continue
        inverse = (d/det, -c/det, (c*ty-d*tx)/det, -b/det, a/det, (b*tx-a*ty)/det)
        layer = frame.transform(canvas.size, Image.Transform.AFFINE, inverse, Image.Resampling.BICUBIC)
        if state["opacity"] < 1:
            layer.putalpha(layer.getchannel("A").point(lambda v: round(v*state["opacity"])))
        canvas.alpha_composite(layer)
    staging = phase.get("staging")
    if staging:
        camera = staging["camera"]
        i = max(i for i, f in enumerate(camera) if f["time"] <= time)
        a, b = camera[i], camera[min(i+1, len(camera)-1)]
        ratio = 0 if a is b else (time-a["time"])/(b["time"]-a["time"])
        zoom = a["zoom"]+(b["zoom"]-a["zoom"])*ratio
        x, y = staging["focus"][0]*16, staging["focus"][1]*9
        canvas = canvas.transform(canvas.size, Image.Transform.AFFINE,
                                  (1/zoom, 0, x*(1-1/zoom), 0, 1/zoom, y*(1-1/zoom)), Image.Resampling.BICUBIC)
    return canvas.convert("RGB")


def calibrate_layout(plan, output, phases):
    """Measure real PNGs, solve widths, then audit geometry before publishing HTML."""
    selected = [i for i, p in enumerate(plan["phases"]) if any(p is s for s in phases)]
    calibrated = copy.deepcopy(plan)
    assets = {a["id"]: a for a in calibrated["assets"]}
    needed = {p["background"] for p in phases} | {t["asset"] for p in phases for t in p["tracks"]}
    config = image_config(require_credentials=False)
    data = {aid: load_asset(plan, assets[aid], output, config) for aid in sorted(needed)}
    # Keep a partial rebuild's full calibrated plan consistent with already
    # available shots. Missing/stale unrelated caches never trigger generation.
    for aid, asset in assets.items():
        if aid not in data and (output/asset_path(asset)).is_file():
            try:
                data[aid] = load_asset(plan, asset, output, config)
            except ValueError:
                pass
    measurements = {aid: png_info(blob, assets[aid]) for aid, blob in data.items()}
    hashes = {aid: hashlib.sha256(blob).hexdigest() for aid, blob in data.items()}
    calibration_path = output/"layout_calibration.json"
    calibration = json.loads(calibration_path.read_text()) if calibration_path.exists() else {}
    if calibration and (not isinstance(calibration, dict) or calibration.get("version") != 1):
        raise ValueError("layout_calibration.json: phiên bản không hợp lệ.")
    if not isinstance(calibration.get("backgrounds", {}), dict):
        raise ValueError("layout_calibration.json.backgrounds: cần object.")
    for aid, background in calibration.get("backgrounds", {}).items():
        if not isinstance(background, dict) or not isinstance(background.get("ground"), dict) or not background["ground"]:
            raise ValueError(f"calibration.{aid}: cần ground và SHA-256 của PNG đã xem.")
        if not isinstance(background.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", background["sha256"]):
            raise ValueError(f"calibration.{aid}: SHA-256 không hợp lệ.")
        for name, polygon in background["ground"].items():
            validate_polygon(polygon, f"calibration.{aid}.{name}")
    report = {"version": 1, "input_digest": digest({"plan": plan, "png": hashes, "calibration": calibration}),
              "png_sha256": hashes, "measurements": measurements, "phases": [], "errors": [],
              "limitations": "Đo alpha và kiểm tra hình học không xác minh ngoại hình/giải phẫu/pose. Vùng nền cần đối chiếu ảnh thật."}
    # Shared sprites must stay calibrated in neighbouring phases too, even when
    # only one HTML file is requested. No unrelated missing images are loaded.
    for phase in calibrated["phases"]:
        if "staging" not in phase:
            continue
        background = calibration.get("backgrounds", {}).get(phase["background"])
        if (background and background.get("sha256") == hashes.get(phase["background"])
                and background.get("view") == phase["staging"]["view"]
                and set(phase["staging"]["ground"]).issubset(background["ground"])):
            phase["staging"]["ground"] = copy.deepcopy(background["ground"])
        for track in phase["tracks"]:
            if track["asset"] in measurements:
                track.setdefault("layout", {})["width"] = measured_track_width(track, phase, measurements)
    for index in selected:
        phase = calibrated["phases"][index]
        entry = {"phase": index+1, "sizes": {}, "proofs": [], "status": "legacy_unmeasured", "issues": []}
        report["phases"].append(entry)
        if "staging" not in phase:
            continue
        staging = phase["staging"]
        background = calibration.get("backgrounds", {}).get(phase["background"])
        if background:
            if background.get("sha256") != hashes[phase["background"]]:
                report["errors"].append(f"Phase {index+1}: PNG nền đổi, phải đo lại layout_calibration.json.")
                continue
            if background.get("view") != staging["view"]:
                report["errors"].append(f"Phase {index+1}: góc nền đã đo không khớp camera.")
                continue
            for name, polygon in background.get("ground", {}).items():
                validate_polygon(polygon, f"calibration.{name}")
            if not set(staging["ground"]).issubset(background.get("ground", {})):
                report["errors"].append(f"Phase {index+1}: thiếu vùng tiếp đất đã đo.")
                continue
            staging["ground"] = copy.deepcopy(background["ground"])
        entry["status"] = "geometry_checked" if background else "needs_background_review"
        for track in phase["tracks"]:
            geometry = track["geometry"]
            info = measurements[track["asset"]]
            box = next(f["bbox"] for f in info["frames"] if f["pose"] == geometry["reference_pose"])
            pixels = box[2]-box[0] if geometry["axis"] == "width" else box[3]-box[1]
            width = track["layout"]["width"]
            entry["sizes"][track["id"]] = {"reference_pose": geometry["reference_pose"], "visible_pixels": pixels,
                "size_m": geometry["size_m"], "frame_width_percent": round(width, 6)}
        times = sorted({round(i*phase["duration"]/max(1, math.ceil(phase["duration"]*10)), 8)
                        for i in range(math.ceil(phase["duration"]*10)+1)} |
                       {f["time"] for t in phase["tracks"] for f in t["keyframes"]})
        seen = set()
        for time in times:
            states = {}
            for track in phase["tracks"]:
                region = track["geometry"].get("ground")
                if region is None:
                    continue
                state = layout_state(phase, assets, track["id"], time, states)
                if state["opacity"] <= 0 or track["keyframes"][max(i for i, f in enumerate(track["keyframes"]) if f["time"] <= time)]["attach"]:
                    continue
                info = measurements[track["asset"]]
                box = next(f["bbox"] for f in info["frames"] if f["pose"] == state["pose"])
                fw, fh = info["frame_size"]
                x, y = layout_point(state, (box[0]+box[2])/2/fw, box[3]/fh)
                if 0 <= x <= 1600 and 0 <= y <= 900 and not inside_polygon(x/16, y/9, staging["ground"][region]):
                    key = (track["id"], region)
                    if key not in seen:
                        entry["issues"].append(f"{track['id']} tại {time:g}s: điểm tiếp đất ngoài vùng {region}.")
                        seen.add(key)
        for track in phase["tracks"]:
            direction = track["geometry"].get("exit")
            if direction:
                state = layout_state(phase, assets, track["id"], phase["duration"])
                xs = [layout_point(state, x, y)[0] for x in (0, 1) for y in (0, 1)]
                if (direction == "right" and min(xs) < 1600) or (direction == "left" and max(xs) > 0):
                    entry["issues"].append(f"{track['id']}: chưa ra hết mép {direction} khi kết thúc.")
        proof_dir = output/"layout_review"/f"phase_{index+1}"
        proof_dir.mkdir(parents=True, exist_ok=True)
        proof_times = sorted({0, phase["duration"], phase["duration"]/2} |
                             {e["start"] for e in phase["events"]} |
                             {f["time"] for t in phase["tracks"] for f in t["keyframes"]})
        if len(proof_times) > 24:
            proof_times = [proof_times[round(i*(len(proof_times)-1)/23)] for i in range(24)]
        for time in proof_times:
            target = proof_dir/f"{time:g}s.jpg"
            layout_snapshot(calibrated, phase, time, output, measurements).save(target, quality=88)
            entry["proofs"].append(str(target.relative_to(output)))
        report["errors"].extend(f"Phase {index+1}: {issue}" for issue in entry["issues"])
    try:
        validate_plan(calibrated)
    except ValueError as error:
        report["errors"].append(str(error))
    (output/"layout_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n")
    if report["errors"]:
        raise ValueError("Hiệu chỉnh ảnh chưa đạt: " + "; ".join(report["errors"]) + ". Xem layout_report.json và layout_review/.")
    (output/"scene_plan.calibrated.json").write_text(json.dumps(calibrated, ensure_ascii=False, indent=2)+"\n")
    measured_count = sum(p["status"] != "legacy_unmeasured" for p in report["phases"])
    print(f"  Đã đo PNG; {measured_count} phase có hiệu chỉnh tỷ lệ/hình học. Xem layout_report.json, layout_review/.", flush=True)
    return calibrated, [calibrated["phases"][i] for i in selected], report


def measured_track_width(track, phase, measurements):
    geometry = track["geometry"]
    info = measurements[track["asset"]]
    box = next(f["bbox"] for f in info["frames"] if f["pose"] == geometry["reference_pose"])
    pixels = box[2]-box[0] if geometry["axis"] == "width" else box[3]-box[1]
    return round(geometry["size_m"]*phase["staging"]["pixels_per_meter"]/pixels*info["frame_size"][0]/16, 6)


STYLE = r"""
*{box-sizing:border-box}body{margin:0;background:#f3f5f8;color:#22314a;font:16px system-ui,sans-serif}
main{max-width:1120px;margin:28px auto;padding:0 20px}h1{font-size:24px;margin:0 0 8px}p{line-height:1.6}
nav{display:flex;gap:10px;flex-wrap:wrap;margin:18px 0}a{color:#1a56b8}button{cursor:pointer;border:0;
background:#224e98;color:white;border-radius:8px;padding:10px 20px;font:inherit}button:disabled{opacity:.5;cursor:wait}
.stage{position:relative;aspect-ratio:16/9;overflow:hidden;isolation:isolate;background:#dce8ec;border-radius:14px}
.scene-world{position:absolute;inset:0;isolation:isolate;will-change:transform}
.background{position:absolute;width:100%;height:100%;object-fit:cover}.sprite{position:absolute;background-repeat:no-repeat;
transform-origin:50% 100%;will-change:transform,left,top}.weather{position:absolute;inset:0;pointer-events:none;z-index:1100}
.drop{position:absolute;display:block;background:linear-gradient(transparent,#d4ecff);width:2px;transform:rotate(15deg)}
.rainbow{position:absolute;left:42%;top:2%;width:53%;aspect-ratio:2/1;overflow:hidden;z-index:1;pointer-events:none}
.rainbow:before{content:"";display:block;width:100%;aspect-ratio:1;border-radius:50%;background:radial-gradient(circle,
transparent 48%,#ac7df0 49% 51%,#73a7ff 52% 54%,#65d1a0 55% 57%,#ffea85 58% 60%,#ffc386 61% 63%,#f79f9f 64% 66%,transparent 67%)}
.controls{display:flex;align-items:center;gap:14px;padding:18px 0}input[type=range]{flex:1;min-width:60px;accent-color:#224e98}
output{font-variant-numeric:tabular-nums;min-width:105px}.caption{min-height:3em}#status{color:#566980}
.state{font-size:14px;color:#566980}.cards{display:grid;gap:12px}.card{padding:18px;background:white;border-radius:12px}
@media(max-width:600px){main{padding:0 12px;margin:16px auto}h1{font-size:20px}.controls{gap:8px}button{padding:10px}}
"""

JAVASCRIPT = r"""
'use strict';
const config = JSON.parse(document.getElementById('scene-data').textContent);
const phase = config.phase;
const stage = document.getElementById('stage');
const world = document.getElementById('world') || stage;
const slider = document.getElementById('time');
const clock = document.getElementById('clock');
const button = document.getElementById('play');
const status = document.getElementById('status');
const caption = document.getElementById('caption');
const rainbow = document.getElementById('rainbow');
const rain = document.getElementById('rain');
const assets = Object.fromEntries(config.assets.map(asset => [asset.id, asset]));
const actors = new Map();
const drops = [];
for (let i = 0; i < 64; i++) {
  const drop = document.createElement('i');
  drop.className = 'drop';
  drop.style.height = `${12 + (i * 13) % 23}px`;
  rain.appendChild(drop);
  drops.push(drop);
}
for (const track of phase.tracks) {
  const asset = assets[track.asset];
  const element = document.createElement('div');
  const [width, height] = asset.size.split('x').map(Number);
  element.className = 'sprite';
  element.dataset.actor = track.id;
  element.setAttribute('role', 'img');
  element.setAttribute('aria-label', track.id);
  element.style.width = `${track.layout?.width ?? track.width}%`;
  element.style.aspectRatio = `${width / asset.columns} / ${height / asset.rows}`;
  element.style.zIndex = track.z;
  element.style.backgroundImage = `url("../${asset.file}")`;
  element.style.backgroundSize = `${asset.columns * 100}% ${asset.rows * 100}%`;
  world.appendChild(element);
  actors.set(track.id, element);
}
function segment(points, time) {
  let index = 0;
  while (index + 1 < points.length && points[index + 1].time <= time) index++;
  const a = points[index], b = points[Math.min(index + 1, points.length - 1)];
  return {a, b, index, ratio: a === b ? 0 : (time - a.time) / (b.time - a.time)};
}
function poseAt(track, time) {
  const {a, index} = segment(track.keyframes, time);
  if (!Array.isArray(a.pose)) return a.pose;
  // Path waypoints must not restart the same walk cycle at its first frame.
  let start = index;
  while (start > 0) {
    const previous = track.keyframes[start - 1];
    if (previous.fps !== a.fps || !Array.isArray(previous.pose) ||
        previous.pose.length !== a.pose.length || previous.pose.some((pose, i) => pose !== a.pose[i])) break;
    start--;
  }
  return a.pose[Math.floor((time-track.keyframes[start].time)*a.fps+1e-9)%a.pose.length];
}
const lerp = (a, b, ratio) => a + (b - a) * ratio;
const tracks = Object.fromEntries(phase.tracks.map(track => [track.id, track]));
const multiply = (p, q) => [p[0]*q[0]+p[2]*q[1], p[1]*q[0]+p[3]*q[1],
                            p[0]*q[2]+p[2]*q[3], p[1]*q[2]+p[3]*q[3]];
const vector = (m, x, y) => [m[0]*x+m[2]*y, m[1]*x+m[3]*y];
function actorState(id, time, states, blendAttachments = true) {
  if (states.has(id)) return states.get(id);
  const track = tracks[id], asset = assets[track.asset];
  const {a, b, ratio} = segment(track.keyframes, time);
  const pose = poseAt(track, time);
  const scale = lerp(a.scale, b.scale, ratio), angle = lerp(a.rotation, b.rotation, ratio)*Math.PI/180;
  const sx = a.flip ? -scale : scale;
  const [sheetWidth, sheetHeight] = asset.size.split('x').map(Number);
  // Fixed design coordinates; percentages keep all geometry responsive to the stage.
  const width = (track.layout?.width ?? track.width)*16;
  const height = width*(sheetHeight/asset.rows)/(sheetWidth/asset.columns);
  const offset = track.layout?.offset ?? [0,0];
  const state = {pose, width, height, anchor:asset.anchor, x:(lerp(a.x,b.x,ratio)+offset[0])*16,
    y:(lerp(a.y,b.y,ratio)+offset[1])*9, opacity:lerp(a.opacity,b.opacity,ratio),
    matrix:[Math.cos(angle)*sx,Math.sin(angle)*sx,-Math.sin(angle)*scale,Math.cos(angle)*scale]};
  if (a.attach) {
    const parent = actorState(a.attach.track, time, states);
    const parentAsset = assets[tracks[a.attach.track].asset];
    const sockets = {...parentAsset.sockets,...tracks[a.attach.track].sockets};
    const socket = sockets[a.attach.socket][parent.pose];
    const same = b.attach && a.attach.track === b.attach.track && a.attach.socket === b.attach.socket;
    const offset = a.attach.offset.map((v,i) => same ? lerp(v,b.attach.offset[i],ratio) : v);
    state.anchor = a.attach.anchor.map((v,i) => same ? lerp(v,b.attach.anchor[i],ratio) : v);
    const delta = vector(parent.matrix, (socket[0]-parent.anchor[0]+offset[0])*parent.width,
                                        (socket[1]-parent.anchor[1]+offset[1])*parent.height);
    state.x = parent.x+delta[0]; state.y = parent.y+delta[1];
    state.matrix = multiply(parent.matrix,state.matrix);
    state.opacity *= parent.opacity;
  }
  const changesBinding = Boolean(a.attach) !== Boolean(b.attach) || (a.attach && b.attach &&
    (a.attach.track !== b.attach.track || a.attach.socket !== b.attach.socket));
  if (blendAttachments && a !== b && changesBinding) {
    // Approach the actual grip location before pickup/release, avoiding a jump at the binding keyframe.
    const start = actorState(id,a.time,new Map(),false), end = actorState(id,b.time,new Map(),false);
    state.x = lerp(start.x,end.x,ratio); state.y = lerp(start.y,end.y,ratio);
    state.anchor = start.anchor.map((v,i) => lerp(v,end.anchor[i],ratio));
    state.matrix = start.matrix.map((v,i) => lerp(v,end.matrix[i],ratio));
    state.opacity = lerp(start.opacity,end.opacity,ratio);
  }
  states.set(id,state);
  return state;
}
function effect(points, time) {
  const {a, b, ratio} = segment(points, time);
  return lerp(a.value, b.value, ratio);
}
let currentTime = 0;
function renderAt(input) {
  const value = Number(input);
  const time = Math.max(0, Math.min(Number.isNaN(value) ? 0 : value, phase.duration));
  currentTime = time;
  if (phase.staging) {
    const {a,b,ratio} = segment(phase.staging.camera,time);
    world.style.transformOrigin = `${phase.staging.focus[0]}% ${phase.staging.focus[1]}%`;
    world.style.transform = `scale(${lerp(a.zoom,b.zoom,ratio)})`;
  }
  const states = new Map();
  for (const track of phase.tracks) {
    const element = actors.get(track.id), asset = assets[track.asset];
    const state = actorState(track.id,time,states), pose = state.pose;
    const frame = asset.poses.indexOf(pose);
    element.style.left = `${state.x/16}%`;
    element.style.top = `${state.y/9}%`;
    element.style.opacity = state.opacity;
    element.style.transformOrigin = `${state.anchor[0]*100}% ${state.anchor[1]*100}%`;
    element.style.transform = `translate(${-state.anchor[0]*100}%, ${-state.anchor[1]*100}%) matrix(${state.matrix.join(',')},0,0)`;
    element.style.backgroundPosition = `${asset.columns === 1 ? 0 : (frame % asset.columns) / (asset.columns - 1) * 100}% ${asset.rows === 1 ? 0 : Math.floor(frame / asset.columns) / (asset.rows - 1) * 100}%`;
    element.dataset.pose = pose;
  }
  rain.style.opacity = effect(phase.rain, time);
  rainbow.style.opacity = effect(phase.rainbow, time);
  drops.forEach((drop, i) => {
    drop.style.left = `${((i * 47.31 - time * 13) % 120 + 120) % 120 - 10}%`;
    drop.style.top = `${((i * 29.73 + time * (55 + i % 7)) % 130 + 130) % 130 - 15}%`;
  });
  slider.value = String(time);
  clock.textContent = `${time.toFixed(2)} / ${phase.duration.toFixed(2)} s`;
  const event = phase.events.findLast(event => event.start <= time && time <= event.end);
  caption.textContent = event ? event.description : '';
  return time;
}
window.renderAt = renderAt;
let playing = false, requestId = null, startTime = 0, startValue = 0;
function pause() {
  playing = false;
  if (requestId !== null) cancelAnimationFrame(requestId);
  requestId = null;
  button.textContent = 'Play';
}
function tick(now) {
  if (!playing) return;
  renderAt(startValue + (now - startTime) / 1000);
  if (currentTime >= phase.duration) pause();
  else requestId = requestAnimationFrame(tick);
}
button.addEventListener('click', () => {
  if (playing) return pause();
  if (currentTime >= phase.duration) renderAt(0);
  playing = true;
  button.textContent = 'Pause';
  startTime = performance.now();
  startValue = currentTime;
  requestId = requestAnimationFrame(tick);
});
slider.addEventListener('input', () => { pause(); renderAt(slider.value); });
renderAt(0);
const sources = [...new Set([phase.background, ...phase.tracks.map(track => track.asset)])];
window.previewReady = Promise.all(sources.map(id => new Promise((resolve, reject) => {
  const image = new Image();
  image.onload = () => {
    const [width,height] = assets[id].size.split('x').map(Number);
    if (image.naturalWidth !== width || image.naturalHeight !== height) {
      reject(new Error(`Sai kích thước ${assets[id].file}`));
    } else resolve();
  };
  image.onerror = () => reject(new Error(`Không tải được ${assets[id].file}`));
  image.src = `../${assets[id].file}`;
}))).then(() => { button.disabled = false; status.textContent = 'Sẵn sàng. Play hoặc kéo thanh thời gian.'; return true; })
  .catch(error => { status.textContent = error.message; return false; });
"""


def write_preview(plan, output, phases):
    authored = plan
    calibration_path = output/"layout_calibration.json"
    calibration_digest = digest(json.loads(calibration_path.read_text()) if calibration_path.exists() else {})
    config = image_config(require_credentials=False)
    # Validate all selected assets before replacing any preview documents.
    needed_assets = {p["background"] for p in phases} | {t["asset"] for p in phases for t in p["tracks"]}
    for asset in plan["assets"]:
        if asset["id"] in needed_assets:
            load_asset(plan, asset, output, config)
    plan, phases, layout_report = calibrate_layout(plan, output, phases)
    enriched = [dict(asset, file=asset_path(asset)) for asset in plan["assets"]]
    for index, phase in enumerate(plan["phases"], 1):
        if not any(phase is selected for selected in phases):
            continue
        folder = output / f"phase_{index}"
        folder.mkdir(parents=True, exist_ok=True)
        scene = json.dumps({"pipeline": PIPELINE_VERSION, "phase": phase, "assets": enriched,
                            "source_phase_digest": digest(authored["phases"][index-1]),
                            "calibration_digest": calibration_digest,
                            "png_sha256": layout_report["png_sha256"]},
                           ensure_ascii=False).replace("<", "\\u003c")
        title = html.escape(f"Phase {index} — {phase['title']}")
        background = next(a for a in enriched if a["id"] == phase["background"])
        review = next(r for r in layout_report["phases"] if r["phase"] == index)
        review_note = {"geometry_checked": "Đã hiệu chỉnh hình học theo PNG và vùng nền đã đo.",
                       "needs_background_review": "Bản nháp: đã đo sprite; vùng mặt đất trong nền còn cần đối chiếu ảnh.",
                       "legacy_unmeasured": "Plan cũ chưa có staging/geometry; chưa hiệu chỉnh bố cục."}[review["status"]]
        document = f'''<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title><link rel="stylesheet" href="style.css"><script src="script.js" defer></script></head>
<body><main><h1>{title}</h1><nav><a href="../index.html">Tất cả phase</a><a href="../kich_ban.md">Kịch bản gốc</a></nav>
<div class="stage" id="stage" aria-label="{title}"><div class="scene-world" id="world"><img class="background" src="../{background['file']}" alt="Bối cảnh">
<div class="rainbow" id="rainbow"></div><div class="weather" id="rain"></div></div></div>
<div class="controls"><button id="play" disabled>Play</button><input id="time" aria-label="Thời gian trong phase" type="range" min="0" max="{phase['duration']}" step="0.01" value="0"><output id="clock"></output></div>
<p id="caption" class="caption"></p><p id="status" role="status">Đang tải ảnh…</p>
<p class="state">{html.escape(review_note)} {html.escape(layout_report['limitations'])} · <a href="../layout_report.json">Báo cáo hiệu chỉnh</a></p>
<p class="state">Đầu: {html.escape(phase['start_state'])}<br>Cuối: {html.escape(phase['end_state'])}</p>
<script type="application/json" id="scene-data">{scene}</script></main></body></html>'''
        (folder / "index.html").write_text(document, encoding="utf-8")
        (folder / "style.css").write_text(STYLE.strip() + "\n", encoding="utf-8")
        (folder / "script.js").write_text(JAVASCRIPT.strip() + "\n", encoding="utf-8")
    cards = []
    for index, phase in enumerate(authored["phases"], 1):
        existing = output / f"phase_{index}" / "index.html"
        try:
            source = existing.read_text(encoding="utf-8")
            saved = re.search(r'<script type="application/json" id="scene-data">(.*?)</script>', source, re.S)
            saved = json.loads(saved.group(1)) if saved else {}
            if (saved.get("pipeline") != PIPELINE_VERSION
                    or saved.get("source_phase_digest") != digest(phase)
                    or saved.get("calibration_digest") != calibration_digest):
                continue
            needed = {phase["background"]} | {t["asset"] for t in phase["tracks"]}
            for asset in plan["assets"]:
                if asset["id"] in needed:
                    blob = load_asset(plan, asset, output, config)
                    if saved.get("png_sha256", {}).get(asset["id"]) != hashlib.sha256(blob).hexdigest():
                        raise ValueError("Preview cũ dùng PNG khác.")
            cards.append(f'<a class="card" href="phase_{index}/index.html">Phase {index}: '
                         f'{html.escape(phase["title"])} · {phase["duration"]:g} giây</a>')
        except (OSError, ValueError, TypeError, AttributeError):
            continue  # Keep old preview files, but do not advertise stale SVG/PNG previews.
    title = html.escape(plan["title"])
    (output / "index.html").write_text(
        f'<!doctype html><html lang="vi"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{title}</title><style>{STYLE}</style><main><h1>{title}</h1>'
        f'<p>{plan["total_duration"]:g} giây · <a href="kich_ban.md">Xem kịch bản AI</a></p>'
        f'<div class="cards">{"".join(cards)}</div></main></html>', encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--script", type=Path, help="File kịch bản đã lưu từ analyze_text.py.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--plan-only", action="store_true", help="Lưu kế hoạch và prompt ảnh, chưa sinh ảnh.")
    mode.add_argument("--html-only", action="store_true", help="Dựng lại HTML bằng kế hoạch/ảnh đã có; dùng cùng --resume.")
    parser.add_argument("--resume", action="store_true", help="Tiếp tục từ kịch bản, kế hoạch và ảnh đã lưu.")
    parser.add_argument("--phase", type=int, help="Chỉ dựng phase này (đánh số từ 1); bỏ qua để dựng tất cả.")
    parser.add_argument("--output", type=Path, default=ROOT / "preview")
    args = parser.parse_args(argv)
    output = args.output.resolve()
    if args.resume and args.script:
        parser.error("--resume dùng kịch bản đã lưu trong output, không đi cùng --script.")
    if not args.resume and not args.script:
        parser.error("Cần --script kich_ban.md hoặc --resume để nhận kịch bản có sẵn.")
    if args.html_only and not args.resume:
        parser.error("--html-only cần --resume để dùng kế hoạch và ảnh đã có.")
    if args.phase is not None and args.phase < 1:
        parser.error("--phase phải từ 1 trở lên.")
    if output.exists() and any(output.iterdir()) and not args.resume:
        parser.error(f"{output} đã có dữ liệu. Dùng --resume hoặc chọn --output khác.")
    script_path, plan_path = output / "kich_ban.md", output / "scene_plan.json"
    if args.resume:
        if not script_path.is_file():
            parser.error(f"Không có kịch bản để tiếp tục: {script_path}.")
        screenplay = script_path.read_text(encoding="utf-8")
    else:
        screenplay = args.script.read_text(encoding="utf-8")
    if not screenplay.strip():
        raise ValueError("Kịch bản rỗng.")
    if not args.plan_only:
        # Fail before analysis requests or changing an existing output when image setup is missing.
        image_config(require_credentials=not args.html_only)
        pillow_image()
    output.mkdir(parents=True, exist_ok=True)
    print(screenplay, flush=True)
    script_path.write_text(screenplay.rstrip() + "\n", encoding="utf-8")
    if args.resume and plan_path.is_file():
        plan = validate_plan(json.loads(plan_path.read_text(encoding="utf-8")))
    else:
        if args.html_only:
            parser.error(f"Không tìm thấy {plan_path}.")
        print("\nĐang phân tích kịch bản thành ảnh dùng chung và timeline…", flush=True)
        plan = analyze_script(screenplay, output)
        plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    prompts = {a["id"]: {"file": asset_path(a), "size": a["size"],
                          "columns": a["columns"], "rows": a["rows"], "anchor": a["anchor"],
                          "transparent": a["kind"] != "backgrounds", "poses": a["poses"],
                          "prompt": image_prompt(plan, a)} for a in plan["assets"]}
    (output / "image_prompts.json").write_text(json.dumps(prompts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\nPhân tích: {len(plan['phases'])} phase, {plan['total_duration']:g} giây, {len(plan['assets'])} ảnh/sprite sheet.", flush=True)
    for index, phase in enumerate(plan["phases"], 1):
        print(f"  Phase {index}: {phase['title']} ({phase['duration']:g}s)", flush=True)
    if args.phase is not None and args.phase > len(plan["phases"]):
        parser.error(f"Kịch bản chỉ có {len(plan['phases'])} phase.")
    phases = [plan["phases"][args.phase - 1]] if args.phase else plan["phases"]
    if args.plan_only:
        print(f"Đã lưu kịch bản, scene_plan.json và image_prompts.json tại {output}.")
        return
    if not args.html_only:
        generate_assets(plan, output, phases, resume=args.resume)
    write_preview(plan, output, phases)
    print(f"Mở {output / 'index.html'} để Play/Pause và tua từng phase.")


if __name__ == "__main__":
    try:
        main()
    except HTTPError as error:
        raise SystemExit(f"API trả HTTP {error.code}. Kiểm tra URL, khóa, model; chạy --resume để tiếp tục.")
    except (URLError, TimeoutError, ValueError, OSError) as error:
        raise SystemExit(f"Lỗi: {error}")
