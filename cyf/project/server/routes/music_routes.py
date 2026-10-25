"""管理员音乐创作管理；沿用项目鉴权和 JSON 响应协议。"""
from flask import Blueprint, request, send_file

from dto.common import success_response
from routes.minimax_endpoint import json_body, minimax_endpoint
from service.minimax_music_service import MiniMaxMusicService

music_bp = Blueprint("music_routes", __name__, url_prefix="/never_guess_my_usage/music")


@music_bp.route("/state", methods=["GET"])
@minimax_endpoint(MiniMaxMusicService)
def state(service):
    return success_response(service.snapshot())


@music_bp.route("/generate", methods=["POST"])
@minimax_endpoint(MiniMaxMusicService, mutating=True)
def generate(service):
    return success_response(service.generate(json_body()), "音乐已生成，音频链接和创作参数已入库。")


@music_bp.route("/cover/preprocess", methods=["POST"])
@minimax_endpoint(MiniMaxMusicService, mutating=True)
def cover_preprocess(service):
    result = service.preprocess_cover(request.form.to_dict(), request.files)
    return success_response(result, "参考音频已上传，已提取歌词，可编辑后生成。")


@music_bp.route("/cover/generate", methods=["POST"])
@minimax_endpoint(MiniMaxMusicService, mutating=True)
def cover_generate(service):
    return success_response(service.generate_cover(json_body()), "翻唱已生成，音频链接和创作参数已入库。")


@music_bp.route("/track/<track_id>", methods=["GET"])
@minimax_endpoint(MiniMaxMusicService)
def track(service, track_id):
    return success_response(service.track(track_id))


@music_bp.route("/audio/<track_id>/<ext>", methods=["GET"])
@minimax_endpoint(MiniMaxMusicService)
def audio(service, track_id, ext):
    response = send_file(service.audio_path(track_id, ext), mimetype="audio/mpeg" if ext == "mp3" else "text/plain",
                         as_attachment=True, download_name=track_id + "." + ext, max_age=0)
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@music_bp.route("/delete", methods=["POST"])
@minimax_endpoint(MiniMaxMusicService, mutating=True)
def delete(service):
    service.delete(json_body().get("id", ""))
    return success_response(msg="音乐记录和本地音频已删除。")
