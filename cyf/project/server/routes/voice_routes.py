"""音色管理：个人音色复刻/合成归本人，全局同步与保活仅管理员。"""
from flask import Blueprint, request, send_file

from dto.common import success_response, to_bool
from routes.minimax_endpoint import json_body, minimax_endpoint
from service.minimax_voice_service import MiniMaxVoiceService
from service.permission_service import ROLE_ADMIN, ROLE_SOUND, current_auth_context

voice_bp = Blueprint("voice_routes", __name__, url_prefix="/never_guess_my_usage/voice")


def _owner_scope():
    """当前请求的 (owner_user_id, is_admin, username)。"""
    context = current_auth_context()
    return context.user_id, context.is_admin, context.username


@voice_bp.route("/state", methods=["GET"])
@minimax_endpoint(MiniMaxVoiceService)
def state(service):
    owner_user_id, is_admin, username = _owner_scope()
    return success_response(service.snapshot(
        owner_user_id=owner_user_id,
        is_admin=is_admin,
        username=username,
    ))


@voice_bp.route("/sync", methods=["POST"])
@minimax_endpoint(MiniMaxVoiceService, mutating=True, required_role=ROLE_ADMIN)
def sync(service):
    result = service.sync()
    return success_response(result, f"连接成功，获取 {result['count']} 个云端音色。")


@voice_bp.route("/clone", methods=["POST"])
@minimax_endpoint(MiniMaxVoiceService, mutating=True)
def clone(service):
    owner_user_id, _is_admin, _username = _owner_scope()
    data = request.form.to_dict()
    for flag in ("consent", "need_noise_reduction", "need_volume_normalization"):
        data[flag] = to_bool(data.get(flag))
    result = service.clone(data, request.files, owner_user_id=owner_user_id)
    return success_response(result, "复刻成功。请在 7 天内正式合成一次，完成音色激活。")


@voice_bp.route("/preference", methods=["POST"])
@minimax_endpoint(MiniMaxVoiceService, mutating=True)
def preference(service):
    owner_user_id, is_admin, username = _owner_scope()
    service.preference(json_body(), owner_user_id=owner_user_id, is_admin=is_admin, username=username)
    return success_response(msg="已保存本地音色设置。")


@voice_bp.route("/delete", methods=["POST"])
@minimax_endpoint(MiniMaxVoiceService, mutating=True)
def delete(service):
    owner_user_id, is_admin, _username = _owner_scope()
    service.delete(json_body(), owner_user_id=owner_user_id, is_admin=is_admin)
    return success_response(msg="云端音色已删除，历史音频仍保留在本机。")


@voice_bp.route("/synthesize", methods=["POST"])
@minimax_endpoint(MiniMaxVoiceService, mutating=True)
def synthesize(service):
    owner_user_id, is_admin, _username = _owner_scope()
    return success_response(service.synthesize(
        json_body(), owner_user_id=owner_user_id, is_admin=is_admin,
    ), "朗读已生成，音频链接和正文已入库。")


@voice_bp.route("/reading/<audio_id>", methods=["GET"])
@minimax_endpoint(MiniMaxVoiceService)
def reading(service, audio_id):
    owner_user_id, is_admin, _username = _owner_scope()
    return success_response(service.reading(audio_id, owner_user_id=owner_user_id, is_admin=is_admin))


@voice_bp.route("/audio/<audio_id>/<ext>", methods=["GET"])
@minimax_endpoint(MiniMaxVoiceService)
def audio(service, audio_id, ext):
    owner_user_id, is_admin, _username = _owner_scope()
    response = send_file(service.audio_path(audio_id, ext, owner_user_id=owner_user_id, is_admin=is_admin),
                         mimetype="audio/mpeg" if ext == "mp3" else "text/plain",
                         as_attachment=True, download_name=audio_id + "." + ext, max_age=0)
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@voice_bp.route("/profile", methods=["GET"])
@minimax_endpoint(MiniMaxVoiceService, required_role=ROLE_ADMIN)
def profile(service):
    return success_response(service.profile())


@voice_bp.route("/keepalive", methods=["GET"])
@minimax_endpoint(MiniMaxVoiceService, required_role=ROLE_ADMIN)
def keepalive(service):
    return success_response(service.keepalive_status())


@voice_bp.route("/keepalive", methods=["POST"])
@minimax_endpoint(MiniMaxVoiceService, mutating=True, required_role=ROLE_ADMIN)
def update_keepalive(service):
    service.update_keepalive(json_body())
    return success_response(msg="保活设置已保存。")


@voice_bp.route("/keepalive/run", methods=["POST"])
@minimax_endpoint(MiniMaxVoiceService, mutating=True, required_role=ROLE_ADMIN)
def run_keepalive(service):
    return success_response(service.run_keepalive(), "保活执行完成。")
