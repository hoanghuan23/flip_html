import copy
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import analyze_text
import generate_preview as preview
from generate_preview import validate_plan


def example_plan():
    assets = [
        {"id": aid, "kind": kind, "size": "100x100", "columns": 1,
         "rows": 1, "poses": ["still"], "prompt": aid}
        for aid, kind in (("house", "backgrounds"), ("road", "backgrounds"),
                          ("door", "objects"), ("girl", "characters"),
                          ("umbrella", "objects"))
    ]
    tracks = [
        {"id": aid, "asset": aid, "width": 20, "z": 1,
         "keyframes": [{"time": t, "x": 50, "y": 80, "pose": "still"}
                       for t in (0, 1)]}
        for aid in ("door", "girl", "umbrella")
    ]
    phases = [
        {"title": background, "duration": 1, "background": background,
         "start_state": "start", "end_state": "end",
         "events": [{"start": 0, "end": 1, "description": "move"}],
         "rain": [{"time": 0, "value": 0}, {"time": 1, "value": 0}],
         "rainbow": [{"time": 0, "value": 0}, {"time": 1, "value": 0}],
         "tracks": copy.deepcopy(tracks if background == "house" else tracks[1:])}
        for background in ("house", "road")
    ]
    return {"title": "test", "style": "test", "total_duration": 2,
            "assets": assets, "phases": phases}


class SceneContinuityTests(unittest.TestCase):
    def setUp(self):
        self.plan = example_plan()
        self.door = self.plan["phases"][0]["tracks"][0]
        self.door["scene_bound"] = True

    def test_scenery_can_stay_behind_when_background_changes(self):
        validate_plan(self.plan)

    def test_unmarked_object_cannot_disappear(self):
        del self.door["scene_bound"]
        with self.assertRaisesRegex(ValueError, "track door"):
            validate_plan(self.plan)

    def test_scenery_cannot_disappear_in_same_background(self):
        self.plan["phases"][1]["background"] = "house"
        with self.assertRaisesRegex(ValueError, "track door"):
            validate_plan(self.plan)

    def test_characters_and_carried_objects_stay_continuous(self):
        for aid in ("girl", "umbrella"):
            with self.subTest(asset=aid):
                plan = copy.deepcopy(self.plan)
                plan["phases"][1]["tracks"] = [
                    t for t in plan["phases"][1]["tracks"] if t["id"] != aid
                ]
                with self.assertRaisesRegex(ValueError, f"track {aid}"):
                    validate_plan(plan)

    def test_character_cannot_be_marked_as_scenery(self):
        self.plan["phases"][0]["tracks"][1]["scene_bound"] = True
        with self.assertRaisesRegex(ValueError, "girl.scene_bound"):
            validate_plan(self.plan)

    def test_marker_must_be_boolean(self):
        self.door["scene_bound"] = "true"
        with self.assertRaisesRegex(ValueError, "door.scene_bound"):
            validate_plan(self.plan)

    def test_persistent_character_cannot_jump(self):
        self.plan["phases"][1]["tracks"][0]["keyframes"][0]["x"] = 70
        with self.assertRaisesRegex(ValueError, "trạng thái đầu girl"):
            validate_plan(self.plan)

    def test_completed_exit_can_reenter_on_a_new_background(self):
        for phase in self.plan["phases"]:
            girl = next(t for t in phase["tracks"] if t["id"] == "girl")
            girl["keyframes"][0]["x"] = 10
            girl["keyframes"][-1]["x"] = 120
        validate_plan(self.plan)

    def test_partial_exit_cannot_reset_position(self):
        girl = self.plan["phases"][0]["tracks"][1]
        girl["keyframes"][-1]["x"] = 105
        with self.assertRaisesRegex(ValueError, "trạng thái đầu girl"):
            validate_plan(self.plan)

    def test_exit_uses_actual_size_and_layout(self):
        for change in ("scale", "layout"):
            with self.subTest(change=change):
                plan = copy.deepcopy(self.plan)
                for phase in plan["phases"]:
                    girl = next(t for t in phase["tracks"] if t["id"] == "girl")
                    if change == "scale":
                        for frame in girl["keyframes"]:
                            frame["scale"] = 3
                    else:
                        girl["layout"] = {"width": 60, "offset": [-5, 0]}
                plan["phases"][0]["tracks"][1]["keyframes"][-1]["x"] = 120
                with self.assertRaisesRegex(ValueError, "trạng thái đầu girl"):
                    validate_plan(plan)

    def test_attached_exit_uses_parent_position(self):
        plan = valid_plan()
        girl = next(a for a in plan["assets"] if a["id"] == "girl")
        girl["sockets"] = {"hand": {"still": [0.7, 0.5]}}
        for phase in plan["phases"]:
            umbrella = next(t for t in phase["tracks"] if t["id"] == "umbrella")
            for frame in umbrella["keyframes"]:
                frame["attach"] = {"track": "girl", "socket": "hand"}
        plan["phases"][0]["tracks"][-1]["keyframes"][-1]["x"] = 120
        with self.assertRaisesRegex(ValueError, "trạng thái đầu umbrella"):
            validate_plan(plan)

    def test_completed_exit_cannot_teleport_in_same_shot(self):
        self.plan["phases"][1]["background"] = "house"
        self.plan["phases"][1]["tracks"].append(copy.deepcopy(self.door))
        self.plan["phases"][0]["tracks"][1]["keyframes"][-1]["x"] = 120
        with self.assertRaisesRegex(ValueError, "trạng thái đầu girl"):
            validate_plan(self.plan)

    def test_completed_exit_still_preserves_carried_binding(self):
        plan = valid_plan()
        girl = next(a for a in plan["assets"] if a["id"] == "girl")
        girl["sockets"] = {"hand": {"still": [0.7, 0.5]}}
        for phase in plan["phases"]:
            for track in phase["tracks"]:
                if track["id"] == "umbrella":
                    for frame in track["keyframes"]:
                        frame["attach"] = {"track": "girl", "socket": "hand"}
        first = plan["phases"][0]
        for track in first["tracks"]:
            if track["id"] in ("girl", "umbrella"):
                track["keyframes"][-1]["x"] = 120
        validate_plan(plan)
        plan["phases"][1]["tracks"][-1]["keyframes"][0]["attach"] = None
        with self.assertRaisesRegex(ValueError, "trạng thái đầu umbrella"):
            validate_plan(plan)

    def test_shared_track_cannot_change_scene_binding(self):
        self.plan["phases"][1]["tracks"].append(copy.deepcopy(self.door))
        self.plan["phases"][1]["tracks"][-1]["scene_bound"] = False
        with self.assertRaisesRegex(ValueError, "của door không liên tục"):
            validate_plan(self.plan)


IMAGE_ENV = {
    "IMAGE_API_BASE_URL": "http://127.0.0.1:8000/generate-image", "IMAGE_API_KEY": "server-test-key",
    "IMAGE_MODEL": "gpt-5.6-luna", "IMAGE_BACKGROUND_SIZE": "1536x1024", "IMAGE_QUALITY": "medium",
}


def png_bytes(size=(1024, 1024), transparent=True, color="gold"):
    from PIL import Image, ImageDraw
    image = Image.new("RGBA" if transparent else "RGB", size, (0, 0, 0, 0) if transparent else "skyblue")
    if transparent:
        ImageDraw.Draw(image).rectangle((size[0]*.3, size[1]*.2, size[0]*.7, size[1]*.9), fill=color)
    stream = io.BytesIO()
    image.save(stream, "PNG")
    return stream.getvalue()


def png_sheet(size, columns, rows, colors):
    from PIL import Image, ImageDraw
    image = Image.new("RGBA", size)
    draw = ImageDraw.Draw(image)
    width, height = size[0]//columns, size[1]//rows
    for index,color in enumerate(colors):
        x,y = index%columns*width,index//columns*height
        draw.rectangle((x+width*.3, y+height*.2, x+width*.7, y+height*.9), fill=color)
    stream = io.BytesIO();image.save(stream,"PNG")
    return stream.getvalue()


def fake_image(prompt, config, *, transparent):
    import re
    if not transparent:
        return png_bytes(preview.dimensions(config["background_size"]), False)
    width,height = map(int,re.search(r"canvas (\d+)x(\d+) pixels",prompt).groups())
    columns,rows = map(int,re.search(r"Grid: (\d+) equal columns by (\d+) equal rows",prompt).groups())
    count = len(re.findall(r"cell \d+:",prompt))
    return png_sheet((width,height),columns,rows,["gold"]*count)


def valid_plan():
    plan = example_plan()
    plan["phases"][0]["tracks"][0]["scene_bound"] = True
    return validate_plan(plan)


def staged_plan():
    plan = valid_plan()
    for phase in plan["phases"]:
        phase["staging"] = {"shot": phase["background"], "view": "side", "transition": "cut",
            "pixels_per_meter":100, "ground":{"floor":[[0,0],[100,0],[100,100],[0,100]]},
            "focus":[50,50], "camera":[{"time":0,"zoom":1},{"time":1,"zoom":1}]}
        for track in phase["tracks"]:
            track["geometry"] = {"reference_pose":"still", "axis":"height", "size_m":1.75,
                "ground":"floor", "baked_poses":[], "views":["side"], "motion":"free"}
    return validate_plan(plan)


class PngImageApiTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict("os.environ", IMAGE_ENV)
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_text_analysis_keeps_existing_api(self):
        response = json.dumps({"success": True, "result": json.dumps(staged_plan())}).encode()
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(analyze_text, "urlopen", return_value=io.BytesIO(response)) as opened:
            preview.analyze_script("screenplay", Path(directory))
        self.assertEqual(opened.call_args.args[0].full_url, analyze_text.API_URL)
        self.assertEqual(json.loads(opened.call_args.args[0].data)["model"], analyze_text.MODEL)

    def test_codex_server_strict_image_contract(self):
        import base64
        data = png_bytes()
        response = {"success":True,"output_format":"png","data":[{"b64_json":base64.b64encode(data).decode()}]}
        for transparent in (True,False):
            with self.subTest(transparent=transparent), patch.object(preview,"request_text") as text_api, \
                    patch.object(preview,"urlopen",return_value=io.BytesIO(json.dumps(response).encode())) as opened:
                self.assertEqual(preview.request_image("draw",preview.image_config(),transparent=transparent),data)
                text_api.assert_not_called()
                request = opened.call_args.args[0]
                self.assertEqual(request.full_url,IMAGE_ENV["IMAGE_API_BASE_URL"])
                self.assertEqual(request.get_header("X-api-key"),"server-test-key")
                self.assertIsNone(request.get_header("Authorization"))
                payload = json.loads(request.data)
                self.assertEqual(set(payload),{"prompt","model"})
                self.assertEqual(payload["model"],"gpt-5.6-luna")
                self.assertIn("draw",payload["prompt"])
                self.assertEqual(opened.call_args.kwargs["timeout"],660)

    def test_missing_configuration_never_calls_text(self):
        with patch.dict("os.environ",{},clear=True),patch.object(preview,"request_text") as text_api:
            with self.assertRaisesRegex(ValueError,"IMAGE_API_BASE_URL, IMAGE_MODEL, IMAGE_API_KEY"):
                preview.image_config()
            text_api.assert_not_called()

    def test_cli_models_are_passed_through_without_image_model_allowlist(self):
        with patch.dict("os.environ",{"IMAGE_MODEL":"another-cli-model"}):
            self.assertEqual(preview.image_config()["model"],"another-cli-model")
        for changes in ({"IMAGE_API_BASE_URL":analyze_text.API_URL},
                        {"IMAGE_API_BASE_URL":"https://api.openai.com/v1"},{"IMAGE_MODEL":"bad model"}):
            with self.subTest(changes=changes),patch.dict("os.environ",changes),self.assertRaises(ValueError):
                preview.image_config()

    def test_bad_image_responses_are_explicit(self):
        for result in ({"success":True,"result":"<svg/>"},
                       {"success":True,"output_format":"png","data":[]},
                       {"success":True,"output_format":"png","data":[{"b64_json":"not-base64"}]},
                       {"success":False,"output_format":"png","data":[{"b64_json":"PHN2Zy8+"}]},
                       {"success":True,"output_format":"png","data":[{"b64_json":"PHN2Zy8+"}]}):
            with self.subTest(result=result), \
                    patch.object(preview,"urlopen",return_value=io.BytesIO(json.dumps(result).encode())), \
                    self.assertRaises(ValueError):
                preview.request_image("draw",preview.image_config(),transparent=True)

    def test_png_dimensions_format_alpha_and_clipping(self):
        asset = valid_plan()["assets"][3]
        frame = preview.normalize_pose(png_bytes(),asset,{"sprite_size":"1024x1024"})
        stream = io.BytesIO();frame.save(stream,"PNG")
        self.assertEqual(preview.png_info(stream.getvalue(),asset)["frame_count"],1)
        for data in (b"<svg/>",png_bytes((200,100)),png_bytes((100,100),False)):
            with self.subTest(length=len(data)),self.assertRaises(ValueError):
                preview.png_info(data,asset)
        from PIL import Image
        for color in ((0,0,0,0),(255,255,255,255)):
            stream=io.BytesIO();Image.new("RGBA",(100,100),color).save(stream,"PNG")
            with self.assertRaises(ValueError):preview.png_info(stream.getvalue(),asset)
        stream=io.BytesIO();image=Image.new("RGBA",(100,100))
        image.putpixel((0,50),(255,0,0,255));image.save(stream,"PNG")
        with self.assertRaisesRegex(ValueError,"chạm biên"):
            preview.png_info(stream.getvalue(),asset)

    def test_invisible_alpha_noise_at_edge_does_not_look_like_clipping(self):
        from PIL import Image
        image=Image.open(io.BytesIO(png_bytes((100,100))))
        image.putpixel((0,50),(255,0,0,1))
        self.assertEqual(preview.frame_info(image,"pose"),[30,20,71,91])
        image.putpixel((0,50),(255,0,0,255))
        with self.assertRaisesRegex(ValueError,"chạm biên"):
            preview.frame_info(image,"pose")

    def test_phase_one_resume_and_html_only(self):
        plan=valid_plan()
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(preview,"request_image",side_effect=fake_image) as ask, \
                patch.object(preview,"request_text") as text_api,contextlib.redirect_stdout(io.StringIO()):
            output=Path(directory)
            (output/"kich_ban.md").write_text("Test story",encoding="utf-8")
            (output/"scene_plan.json").write_text(json.dumps(plan),encoding="utf-8")
            original=(output/"scene_plan.json").read_bytes()
            preview.main(["--resume","--phase","1","--output",directory])
            self.assertEqual(ask.call_count,4)
            self.assertTrue((output/"assets/characters/girl.png").is_file())
            self.assertFalse((output/"assets/backgrounds/road.png").exists())
            self.assertIn("house.png",(output/"phase_1/index.html").read_text())
            self.assertFalse((output/"phase_2/index.html").exists())
            self.assertEqual((output/"scene_plan.json").read_bytes(),original)
            ask.reset_mock()
            preview.main(["--resume","--phase","1","--output",directory])
            with patch.dict("os.environ",{"IMAGE_API_KEY":""}):
                preview.main(["--resume","--html-only","--phase","1","--output",directory])
            ask.assert_not_called();text_api.assert_not_called()

    def test_sheet_order_empty_cells_and_shared_baseline(self):
        from PIL import Image
        plan=valid_plan();girl=plan["assets"][3]
        girl.update(size="300x100",columns=3,poses=["still","crouch"])
        # The CLI returns a larger canvas; accept its checked grid, then normalize uniformly.
        data=png_sheet((600,200),3,1,["red","blue"])
        source=Image.open(io.BytesIO(data))
        source.putpixel((500,50),(255,0,0,preview.ALPHA_NOISE_FLOOR-1))
        stream=io.BytesIO();source.save(stream,"PNG");data=stream.getvalue()
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(preview,"request_image",return_value=data) as ask, \
                contextlib.redirect_stdout(io.StringIO()):
            output=Path(directory);phase={"background":"unused","tracks":[{"asset":"girl"}]}
            preview.generate_assets(plan,output,[phase])
            data=preview.load_asset(plan,girl,output,preview.image_config())
            info=preview.png_info(data,girl)
            self.assertEqual([f["pose"] for f in info["frames"]],["still","crouch"])
            self.assertEqual(info["frame_size"],[100,100])
            self.assertEqual(info["frames"][0]["bbox"][3],info["frames"][1]["bbox"][3])
            self.assertEqual(ask.call_count,1)
            self.assertIn("cell 1: still; cell 2: crouch",ask.call_args.args[0])
            image=Image.open(io.BytesIO(data))
            self.assertEqual(image.getpixel((50,50))[:3],(255,0,0))
            self.assertEqual(image.getpixel((150,50))[:3],(0,0,255))
            self.assertIsNone(image.crop((200,0,300,100)).getchannel("A").getbbox())
            self.assertEqual((output/"assets/characters/.source/girl.png").read_bytes(),ask.return_value)
            image.putpixel((250,50),(255,0,0,255));stream=io.BytesIO();image.save(stream,"PNG")
            with self.assertRaisesRegex(ValueError,"ô thừa"):
                preview.png_info(stream.getvalue(),girl)

    def test_raw_unused_cells_reject_visible_pixels(self):
        from PIL import Image
        asset=valid_plan()["assets"][3]
        asset.update(size="200x100",columns=2,poses=["still"])
        for alpha in (preview.ALPHA_NOISE_FLOOR,255):
            with self.subTest(alpha=alpha):
                image=Image.open(io.BytesIO(png_sheet((200,100),2,1,["red"])))
                image.putpixel((150,50),(255,0,0,alpha))
                stream=io.BytesIO();image.save(stream,"PNG")
                with self.assertRaisesRegex(ValueError,"ô thừa"):
                    preview.raw_sheet_info(stream.getvalue(),asset)

    def test_raw_sheet_rejects_wrong_grid_clipping_empty_and_fake_alpha(self):
        from PIL import Image
        asset=valid_plan()["assets"][3]
        asset.update(size="200x100",columns=2,poses=["still","walk"])
        invalid=[png_sheet((200,100),2,1,["red"]),png_bytes((200,100),False),
                 png_sheet((200,200),2,1,["red","blue"])]
        for data in invalid:
            with self.assertRaises(ValueError):preview.raw_sheet_info(data,asset)

    def test_invalid_cache_regenerates_and_svg_is_preserved(self):
        plan=valid_plan();phase=[plan["phases"][0]]
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(preview,"request_image",side_effect=fake_image) as ask, \
                contextlib.redirect_stdout(io.StringIO()):
            output=Path(directory);old=output/"assets/characters/girl.svg"
            old.parent.mkdir(parents=True);old.write_text("old SVG")
            old.with_suffix(".meta.json").write_text("old metadata")
            preview.generate_assets(plan,output,phase,resume=True)
            target=output/"assets/characters/girl.png";target.write_bytes(b"broken PNG")
            with self.assertRaisesRegex(ValueError,"file/metadata"):
                preview.write_preview(plan,output,phase)
            preview.generate_assets(plan,output,phase,resume=True)
            preview.load_asset(plan,plan["assets"][3],output,preview.image_config())
            self.assertEqual(old.read_text(),"old SVG")
            self.assertEqual(old.with_suffix(".meta.json").read_text(),"old metadata")
            self.assertEqual(ask.call_count,4)
            preview.metadata_path(target).write_text("{bad-json")
            preview.generate_assets(plan,output,phase,resume=True)
            self.assertEqual(ask.call_count,4)
            for field,value in (("IMAGE_MODEL","another-cli-model"),("IMAGE_QUALITY","high")):
                with patch.dict("os.environ",{field:value}),self.assertRaises(ValueError):
                    preview.load_asset(plan,plan["assets"][3],output,preview.image_config())
            plan["assets"][3]["prompt"]+="changed"
            preview.generate_assets(plan,output,phase,resume=True)
            self.assertGreater(ask.call_count,4)

    def test_interrupted_generation_resumes_assets(self):
        plan=valid_plan();phases=[plan["phases"][0]]
        with tempfile.TemporaryDirectory() as directory,contextlib.redirect_stdout(io.StringIO()):
            output=Path(directory)
            with patch.object(preview,"request_image",side_effect=[png_bytes((1536,1024),False),TimeoutError("interrupted")]):
                with self.assertRaises(TimeoutError):preview.generate_assets(plan,output,phases,resume=True)
            with patch.object(preview,"request_image",side_effect=fake_image) as ask:
                preview.generate_assets(plan,output,phases,resume=True)
                self.assertEqual(ask.call_count,3)

    def test_rejected_raw_png_kept_for_inspection_but_never_used_as_cache(self):
        plan=valid_plan();girl=plan["assets"][3]
        phase={"background":"unused","tracks":[{"asset":"girl"}]}
        with tempfile.TemporaryDirectory() as directory,contextlib.redirect_stdout(io.StringIO()):
            output=Path(directory)
            with patch.object(preview,"request_image",return_value=png_bytes((100,100),False)):
                with self.assertRaises(ValueError):preview.generate_assets(plan,output,[phase],resume=True)
            target=output/"assets/characters/.source/girl.png"
            self.assertTrue(target.is_file());self.assertFalse(preview.metadata_path(target).exists())
            with patch.object(preview,"request_image",side_effect=fake_image) as ask:
                preview.generate_assets(plan,output,[phase],resume=True)
                self.assertEqual(ask.call_count,1)

class AttachmentTests(unittest.TestCase):
    def setUp(self):
        self.plan = valid_plan()
        self.girl = self.plan["assets"][3]
        self.girl["sockets"] = {"hand": {"still": [0.6, 0.5]}}
        for phase in self.plan["phases"]:
            umbrella = next(t for t in phase["tracks"] if t["id"] == "umbrella")
            for frame in umbrella["keyframes"]:
                frame["attach"] = {"track": "girl", "socket": "hand", "anchor": [0.5, 0.8]}

    def test_valid_attachment_and_default_offset(self):
        validate_plan(self.plan)
        self.assertEqual(self.plan["phases"][0]["tracks"][-1]["keyframes"][0]["attach"]["offset"], [0, 0])

    def test_character_can_sit_on_vehicle_and_exit_with_it(self):
        for phase in self.plan["phases"]:
            girl = next(t for t in phase["tracks"] if t["id"] == "girl")
            vehicle = next(t for t in phase["tracks"] if t["id"] == "umbrella")
            vehicle["sockets"] = {"seat": {"still": [0.4, 0.6]}}
            for frame in vehicle["keyframes"]:
                frame["attach"] = None
            for frame in girl["keyframes"]:
                frame["attach"] = {"track": "umbrella", "socket": "seat", "anchor": [0.3, 0.65]}
                frame["x"] = 399  # The parent's position controls an attached rider.
        validate_plan(self.plan)
        assets = {a["id"]: a for a in self.plan["assets"]}
        first = self.plan["phases"][0]
        self.assertFalse(preview.endpoint_outside_stage(first, assets, "girl"))
        vehicle = next(t for t in first["tracks"] if t["id"] == "umbrella")
        vehicle["keyframes"][-1]["x"] = 106
        self.assertFalse(preview.endpoint_outside_stage(first, assets, "girl"))
        vehicle["keyframes"][-1]["x"] = 125
        self.assertTrue(preview.endpoint_outside_stage(first, assets, "girl"))
        validate_plan(self.plan)  # A completed exit permits the next camera position.

    def test_track_socket_calibration_does_not_invalidate_generated_images(self):
        self.girl["sockets"] = {}
        for phase in self.plan["phases"]:
            girl = next(t for t in phase["tracks"] if t["id"] == "girl")
            girl["sockets"] = {"hand":{"still":[0.7,0.6]}}
        validate_plan(self.plan)
        recipe = preview.asset_recipe(self.plan,self.girl,{"model":"cli-model"})
        self.assertEqual(recipe["asset"]["sockets"],{})
        before = preview.digest(recipe)
        for phase in self.plan["phases"]:
            next(t for t in phase["tracks"] if t["id"] == "girl")["sockets"]["hand"]["still"] = [0.6,0.7]
        validate_plan(self.plan)
        self.assertEqual(preview.digest(preview.asset_recipe(self.plan,self.girl,{"model":"cli-model"})),before)

    def test_missing_socket_or_parent(self):
        for key, value in (("track", "missing"), ("socket", "missing")):
            plan = copy.deepcopy(self.plan)
            plan["phases"][0]["tracks"][-1]["keyframes"][0]["attach"][key] = value
            with self.assertRaises(ValueError):
                validate_plan(plan)

    def test_sockets_require_all_poses(self):
        self.girl["sockets"]["hand"] = {}
        with self.assertRaisesRegex(ValueError, "tất cả poses"):
            validate_plan(self.plan)

    def test_attachment_cycle(self):
        umbrella = self.plan["assets"][4]
        umbrella["sockets"] = {"grip": {"still": [0.5, 0.5]}}
        track = self.plan["phases"][0]["tracks"][-1]
        track["keyframes"][0]["attach"] = {"track": "umbrella", "socket": "grip"}
        with self.assertRaisesRegex(ValueError, "chu trình"):
            validate_plan(self.plan)

    def test_phase_transition_cannot_change_attachment(self):
        self.plan["phases"][1]["tracks"][-1]["keyframes"][0]["attach"] = None
        with self.assertRaisesRegex(ValueError, "trạng thái đầu umbrella"):
            validate_plan(self.plan)


class StagingContractTests(unittest.TestCase):
    def test_camera_cut_can_reproject_visible_actors(self):
        plan = staged_plan()
        girl = plan["phases"][1]["tracks"][0]
        girl.update(width=30, z=5, layout={"offset":[2,3]})
        girl["keyframes"][0].update(x=25,y=65,scale=.8)
        validate_plan(plan)

    def test_continuous_camera_cannot_replace_background(self):
        plan = staged_plan()
        plan["phases"][1]["staging"] = copy.deepcopy(plan["phases"][0]["staging"])
        plan["phases"][1]["staging"]["transition"] = "continuous"
        with self.assertRaisesRegex(ValueError,"giữ nền"):
            validate_plan(plan)

    def test_continuous_zoom_must_match(self):
        plan = staged_plan()
        second = plan["phases"][1]
        second["background"] = "house"
        second["staging"] = copy.deepcopy(plan["phases"][0]["staging"])
        second["staging"].update(transition="continuous")
        second["staging"]["camera"][0]["zoom"] = 1.1
        with self.assertRaisesRegex(ValueError,"zoom đầu"):
            validate_plan(plan)

    def test_sprite_view_must_match_camera(self):
        plan = staged_plan()
        plan["phases"][0]["staging"]["view"] = "overhead"
        with self.assertRaisesRegex(ValueError,"góc sprite"):
            validate_plan(plan)

    def test_human_and_sedan_cannot_have_arbitrary_physical_sizes(self):
        for role,axis,size in [('adult','height',4),('sedan','width',1.5)]:
            with self.subTest(role=role):
                plan=staged_plan()
                plan['phases'][0]['tracks'][1]['geometry'].update(role=role,axis=axis,size_m=size)
                with self.assertRaisesRegex(ValueError,'kích thước'):
                    validate_plan(plan)

    def test_baked_fallen_pose_cannot_rotate_again(self):
        plan = staged_plan()
        track = plan["phases"][0]["tracks"][1]
        track["geometry"]["baked_poses"] = ["still"]
        track["keyframes"][0]["rotation"] = -30
        with self.assertRaisesRegex(ValueError,"không xoay thêm"):
            validate_plan(plan)

    def test_constant_motion_cannot_slow_in_last_segment(self):
        plan = staged_plan()
        track = plan["phases"][0]["tracks"][1]
        track["geometry"]["motion"] = "constant"
        track["keyframes"] = [dict(track["keyframes"][0],time=t,x=x) for t,x in [(0,0),(.5,40),(1,50)]]
        with self.assertRaisesRegex(ValueError,"vận tốc"):
            validate_plan(plan)

    def test_walking_left_requires_correct_facing(self):
        plan = staged_plan()
        track = plan["phases"][0]["tracks"][1]
        track["geometry"].update(locomotion_poses=["still"],forward="right")
        track["keyframes"][-1]["x"] = 25
        with self.assertRaisesRegex(ValueError,"ngược đường đi"):
            validate_plan(plan)
        for frame in track["keyframes"]:frame["flip"]=True
        validate_plan(plan)

    def test_ai_analysis_repairs_missing_spatial_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            ask = unittest.mock.Mock(side_effect=[json.dumps(valid_plan()),json.dumps(staged_plan())])
            result = preview.analyze_script("story",Path(directory),ask)
            self.assertEqual(ask.call_count,2)
            self.assertIn("staging",ask.call_args.args[0])
            self.assertIn("staging",result["phases"][0])


class LayoutCalibrationTests(unittest.TestCase):
    def setUp(self):
        self.plan = staged_plan()
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.output = Path(self.directory.name)
        self.environment = patch.dict("os.environ",IMAGE_ENV)
        self.environment.start();self.addCleanup(self.environment.stop)
        self.quiet = contextlib.redirect_stdout(io.StringIO())
        self.quiet.__enter__();self.addCleanup(self.quiet.__exit__,None,None,None)
        with patch.object(preview,"request_image",side_effect=fake_image):
            preview.generate_assets(self.plan,self.output,self.plan["phases"])

    def calibrate(self):
        return preview.calibrate_layout(self.plan,self.output,self.plan["phases"])

    def calibration(self, polygon=None, sha=None):
        import hashlib
        ground = {"floor":polygon or [[0,0],[100,0],[100,100],[0,100]]}
        backgrounds = {}
        for aid in ("house","road"):
            asset = next(a for a in self.plan["assets"] if a["id"] == aid)
            blob = (self.output/preview.asset_path(asset)).read_bytes()
            backgrounds[aid] = {"sha256":sha or hashlib.sha256(blob).hexdigest(),"view":"side","ground":ground}
        (self.output/"layout_calibration.json").write_text(json.dumps({"version":1,"backgrounds":backgrounds}))

    def test_real_alpha_sets_physical_scale_without_mutating_authored_plan(self):
        original = copy.deepcopy(self.plan)
        calibrated, phases, report = self.calibrate()
        self.assertEqual(self.plan,original)
        girl = phases[0]["tracks"][1]
        info = report["measurements"]["girl"]
        box = info["frames"][0]["bbox"]
        visible_height = (box[3]-box[1])/info["frame_size"][0]*girl["layout"]["width"]*16
        self.assertAlmostEqual(visible_height,175,places=4)
        self.assertEqual(report["phases"][0]["status"],"needs_background_review")
        from PIL import Image
        with Image.open(self.output/report["phases"][0]["proofs"][0]) as proof:
            self.assertEqual(proof.size,(1600,900))
        self.assertEqual(self.calibrate()[0],calibrated)

    def test_changed_png_is_remeasured(self):
        from PIL import Image, ImageDraw
        first = self.calibrate()[0]["phases"][0]["tracks"][1]["layout"]["width"]
        asset = next(a for a in self.plan["assets"] if a["id"] == "girl")
        image = Image.new("RGBA",(100,100))
        ImageDraw.Draw(image).rectangle((35,54,64,93),fill="red")
        stream=io.BytesIO();image.save(stream,"PNG");blob=stream.getvalue()
        preview.save_cached(self.output/preview.asset_path(asset),blob,
            preview.digest(preview.asset_recipe(self.plan,asset,preview.image_config())),preview.png_info(blob,asset))
        second = self.calibrate()[0]["phases"][0]["tracks"][1]["layout"]["width"]
        self.assertGreater(second,first)

    def test_stale_background_calibration_is_rejected(self):
        self.calibration(sha="0"*64)
        with self.assertRaisesRegex(ValueError,"PNG nền đổi"):
            self.calibrate()

    def test_off_ground_prevents_replacing_preview(self):
        self.calibration(polygon=[[0,90],[100,90],[100,100],[0,100]])
        folder=self.output/"phase_1";folder.mkdir()
        previous=folder/"index.html";previous.write_text("previous preview")
        with self.assertRaisesRegex(ValueError,"ngoài vùng floor"):
            preview.write_preview(self.plan,self.output,self.plan["phases"])
        self.assertEqual(previous.read_text(),"previous preview")
        self.assertTrue(json.loads((self.output/"layout_report.json").read_text())["errors"])

    def test_exit_uses_calibrated_frame_not_only_anchor(self):
        track=self.plan["phases"][0]["tracks"][1]
        track["geometry"]["exit"]="right"
        track["keyframes"][-1]["x"]=105
        with self.assertRaisesRegex(ValueError,"chưa ra hết"):
            self.calibrate()

    def test_measured_ground_status_and_partial_build_keep_other_cards(self):
        self.calibration()
        preview.write_preview(self.plan,self.output,self.plan["phases"])
        preview.write_preview(self.plan,self.output,[self.plan["phases"][0]])
        index=(self.output/"index.html").read_text()
        self.assertIn('href="phase_2/index.html"',index)
        report=json.loads((self.output/"layout_report.json").read_text())
        self.assertEqual(report["phases"][0]["status"],"geometry_checked")


class AnimationRuntimeTests(unittest.TestCase):
    def test_time_pose_anchor_attachment_transforms_and_scrubbing(self):
        import subprocess
        import shutil
        if not shutil.which("node"):
            self.skipTest("Node.js needed for JavaScript runtime verification")
        plan = valid_plan()
        phase = plan["phases"][0]
        phase["tracks"] = [t for t in phase["tracks"] if t["id"] != "door"]
        girl, umbrella = phase["tracks"]
        plan["assets"][3]["sockets"] = {"hand": {"still": [0.75, 0.5], "walk": [0.8, 0.4]}}
        plan["assets"][3].update(poses=["still", "walk"], size="200x100", columns=2)
        for frame in girl["keyframes"]:
            frame.update(rotation=90, scale=2, flip=True)
        girl["keyframes"][0].update(pose=["still", "walk"], fps=2)
        for frame in umbrella["keyframes"]:
            frame["attach"] = {"track": "girl", "socket": "hand", "anchor": [0.5, 0.8], "offset": [0, 0]}
        config = {"phase": phase, "assets": [dict(a, file=preview.asset_path(a)) for a in plan["assets"]]}
        harness = r'''
const assert = require('node:assert/strict');
const elements = new Map();
function element() { return {style:{},dataset:{},children:[],disabled:true,
  appendChild(e){this.children.push(e)},setAttribute(){},addEventListener(){}}; }
for(const id of ['stage','scene-data','time','clock','play','status','caption','rainbow','rain']) elements.set(id,element());
elements.get('scene-data').textContent=JSON.stringify(CONFIG);
global.document={getElementById:id=>elements.get(id),createElement:()=>element()};
global.window={}; global.Image=class {set src(v){this.naturalWidth=100;this.naturalHeight=100;queueMicrotask(()=>this.onload())}};
global.requestAnimationFrame=()=>1; global.cancelAnimationFrame=()=>{};
'''.replace("CONFIG", json.dumps(config))
        checks = r'''
const girlElement=actors.get('girl'), prop=actors.get('umbrella');
assert.equal(renderAt(-1),0); assert.equal(girlElement.dataset.pose,'still');
// Socket offset (80,-140.8), flipped/scaled then rotated 90deg => (281.6,-160).
assert.ok(Math.abs(parseFloat(prop.style.left)-67.6)<1e-8);
assert.ok(Math.abs(parseFloat(prop.style.top)-(720-160)/9)<1e-8);
assert.equal(prop.style.transformOrigin,'50% 80%');
assert.equal(renderAt(.6),.6); assert.equal(girlElement.dataset.pose,'walk');
console.log(JSON.stringify(actorState('umbrella',.6,new Map())));
const atSix=prop.style.left;
renderAt(.1); renderAt(.6); assert.equal(prop.style.left,atSix);
assert.equal(renderAt(99),1); assert.equal(girlElement.dataset.pose,'still');
assert.equal(renderAt('invalid'),0);
// Switching from a world-space prop to a hand binding must approach the same endpoint.
tracks.umbrella.keyframes[0].attach=null;
const before=actorState('umbrella',1-1e-8,new Map()), at=actorState('umbrella',1,new Map());
assert.ok(Math.abs(before.x-at.x)<1e-4);
assert.ok(Math.abs(before.y-at.y)<1e-4);
assert.ok(Math.abs(before.anchor[1]-at.anchor[1])<1e-4);
tracks.girl.layout={width:30,offset:[4,-3]};
const calibrated=actorState('girl',1,new Map());
assert.equal(calibrated.width,480);
assert.equal(calibrated.x,864);
assert.equal(calibrated.y,693);
// Frequent movement waypoints must not keep restarting the first walking image.
const walking=tracks.girl.keyframes[0];
tracks.girl.keyframes=[0,.1,.2,.3,.4,1].map((time,i)=>({...walking,time,x:20+i,
  fps:8,pose:time===1?'still':['still','walk']}));
renderAt(.06);assert.equal(girlElement.dataset.pose,'still');
const firstFrame=girlElement.style.backgroundPosition;
renderAt(.13);assert.equal(girlElement.dataset.pose,'walk');
assert.notEqual(girlElement.style.backgroundPosition,firstFrame);
renderAt(.26);assert.equal(girlElement.dataset.pose,'still');
renderAt(.38);assert.equal(girlElement.dataset.pose,'walk');
// The actual Play loop uses the same alternating frames as direct scrubbing.
playing=true;startTime=0;startValue=0;tick(130);
assert.equal(girlElement.dataset.pose,'walk');
tick(260);assert.equal(girlElement.dataset.pose,'still');
pause();
renderAt(.13);assert.equal(girlElement.dataset.pose,'walk');
phase.staging={focus:[50,65],camera:[{time:0,zoom:1.1},{time:1,zoom:1}]};
renderAt(.5);assert.equal(world.style.transform,'scale(1.05)');
assert.equal(world.style.transformOrigin,'50% 65%');
'''
        result = subprocess.run(["node", "-e", harness + preview.JAVASCRIPT + checks], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        expected=preview.layout_state(phase,{a['id']:a for a in plan['assets']},'umbrella',.6)
        actual=json.loads(result.stdout)
        for key in ('x','y','width','height','opacity'):
            self.assertAlmostEqual(actual[key],expected[key])
        for key in ('anchor','matrix'):
            for a,b in zip(actual[key],expected[key]):self.assertAlmostEqual(a,b)

if __name__ == "__main__":
    unittest.main()
