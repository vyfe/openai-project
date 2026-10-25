"""管理员音色管理；沿用项目鉴权和 JSON 响应协议。"""
from flask import Blueprint, request, send_file

from dto.common import success_response, to_bool
from routes.minimax_endpoint import json_body, minimax_endpoint
from service.minimax_voice_service import MiniMaxVoiceService

voice_bp = Blueprint("voice_routes", __name__, url_prefix="/never_guess_my_usage/voice")


@voice_bp.route("/state", methods=["GET"])
@minimax_endpoint(MiniMaxVoiceService)
def state(service):
    return success_response(service.snapshot())


@voice_bp.route("/sync", methods=["POST"])
@minimax_endpoint(MiniMaxVoiceService, mutating=True)
def sync(service):
    result = service.sync()
    return success_response(result, f"连接成功，获取 {result['count']} 个云端音色。")


@voice_bp.route("/clone", methods=["POST"])
@minimax_endpoint(MiniMaxVoiceService, mutating=True)
def clone(service):
    data = request.form.to_dict()
    for flag in ("consent", "need_noise_reduction", "need_volume_normalization"):
        data[flag] = to_bool(data.get(flag))
    result = service.clone(data, request.files)
    return success_response(result, "复刻成功。请在 7 天内正式合成一次，完成音色激活。")


@voice_bp.route("/preference", methods=["POST"])
@minimax_endpoint(MiniMaxVoiceService, mutating=True)
def preference(service):
    service.preference(json_body())
    return success_response(msg="已保存本地音色设置。")


@voice_bp.route("/delete", methods=["POST"])
@minimax_endpoint(MiniMaxVoiceService, mutating=True)
def delete(service):
    service.delete(json_body())
    return success_response(msg="云端音色已删除，历史音频仍保留在本机。")


@voice_bp.route("/synthesize", methods=["POST"])
@minimax_endpoint(MiniMaxVoiceService, mutating=True)
def synthesize(service):
    return success_response(service.synthesize(json_body()), "朗读已生成，音频链接和正文已入库。")


@voice_bp.route("/reading/<audio_id>", methods=["GET"])
@minimax_endpoint(MiniMaxVoiceService)
def reading(service, audio_id):
    return success_response(service.reading(audio_id))


@voice_bp.route("/audio/<audio_id>/<ext>", methods=["GET"])
@minimax_endpoint(MiniMaxVoiceService)
def audio(service, audio_id, ext):
    response = send_file(service.audio_path(audio_id, ext), mimetype="audio/mpeg" if ext == "mp3" else "text/plain",
                         as_attachment=True, download_name=audio_id + "." + ext, max_age=0)
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@voice_bp.route("/profile", methods=["GET"])
@minimax_endpoint(MiniMaxVoiceService)
def profile(service):
    return success_response(service.profile())


@voice_bp.route("/keepalive", methods=["GET"])
@minimax_endpoint(MiniMaxVoiceService)
def keepalive(service):
    return success_response(service.keepalive_status())


@voice_bp.route("/keepalive", methods=["POST"])
@minimax_endpoint(MiniMaxVoiceService, mutating=True)
def update_keepalive(service):
    service.update_keepalive(json_body())
    return success_response(msg="保活设置已保存。")


@voice_bp.route("/keepalive/run", methods=["POST"])
@minimax_endpoint(MiniMaxVoiceService, mutating=True)
def run_keepalive(service):
    return success_response(service.run_keepalive(), "保活执行完成。")
