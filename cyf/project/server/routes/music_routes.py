"""音乐创作：个人作品归本人，生成 / 翻唱需要 sound 角色。"""
from flask import Blueprint, request, send_file

from dto.common import success_response
from routes.minimax_endpoint import json_body, minimax_endpoint
from service.minimax_music_service import MiniMaxMusicService
from service.permission_service import current_auth_context

music_bp = Blueprint("music_routes", __name__, url_prefix="/never_guess_my_usage/music")


def _owner_scope():
    """当前请求的 (owner_user_id, is_admin)。"""
    context = current_auth_context()
    return context.user_id, context.is_admin


@music_bp.route("/state", methods=["GET"])
@minimax_endpoint(MiniMaxMusicService)
def state(service):
    owner_user_id, is_admin = _owner_scope()
    return success_response(service.snapshot(owner_user_id=owner_user_id, is_admin=is_admin))


@music_bp.route("/generate", methods=["POST"])
@minimax_endpoint(MiniMaxMusicService, mutating=True)
def generate(service):
    owner_user_id, _is_admin = _owner_scope()
    return success_response(service.generate(json_body(), owner_user_id=owner_user_id), "音乐已生成，音频链接和创作参数已入库。")


@music_bp.route("/cover/preprocess", methods=["POST"])
@minimax_endpoint(MiniMaxMusicService, mutating=True)
def cover_preprocess(service):
    owner_user_id, _is_admin = _owner_scope()
    result = service.preprocess_cover(request.form.to_dict(), request.files, owner_user_id=owner_user_id)
    return success_response(result, "参考音频已上传，已提取歌词，可编辑后生成。")


@music_bp.route("/cover/generate", methods=["POST"])
@minimax_endpoint(MiniMaxMusicService, mutating=True)
def cover_generate(service):
    owner_user_id, is_admin = _owner_scope()
    return success_response(service.generate_cover(json_body(), owner_user_id=owner_user_id, is_admin=is_admin), "翻唱已生成，音频链接和创作参数已入库。")


@music_bp.route("/track/<track_id>", methods=["GET"])
@minimax_endpoint(MiniMaxMusicService)
def track(service, track_id):
    owner_user_id, is_admin = _owner_scope()
    return success_response(service.track(track_id, owner_user_id=owner_user_id, is_admin=is_admin))


@music_bp.route("/audio/<track_id>/<ext>", methods=["GET"])
@minimax_endpoint(MiniMaxMusicService)
def audio(service, track_id, ext):
    owner_user_id, is_admin = _owner_scope()
    response = send_file(service.audio_path(track_id, ext, owner_user_id=owner_user_id, is_admin=is_admin),
                         mimetype="audio/mpeg" if ext == "mp3" else "text/plain",
                         as_attachment=True, download_name=track_id + "." + ext, max_age=0)
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@music_bp.route("/delete", methods=["POST"])
@minimax_endpoint(MiniMaxMusicService, mutating=True)
def delete(service):
    owner_user_id, is_admin = _owner_scope()
    service.delete(json_body().get("id", ""), owner_user_id=owner_user_id, is_admin=is_admin)
    return success_response(msg="音乐记录和本地音频已删除。")
