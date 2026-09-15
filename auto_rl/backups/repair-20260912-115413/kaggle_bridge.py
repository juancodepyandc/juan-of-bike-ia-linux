"""Small authenticated subprocess, run by cycle_app_venv (never exports keys)."""
import json
import sys
from kaggle.api.kaggle_api_extended import KaggleApi


def main():
    api = KaggleApi()
    api.authenticate()
    command = sys.argv[1]
    if command == "quota":
        q = api.quota_view()
        g = q.gpu_quota
        print(json.dumps({"remaining_seconds": max(0, (g.total_time_allowed - g.time_used - g.time_reserved).total_seconds()),
                          "used_seconds": g.time_used.total_seconds(), "reserved_seconds": g.time_reserved.total_seconds(),
                          "refresh": str(q.quota_refresh_time)}))
    elif command == "push":
        r = api.kernels_push(sys.argv[2], timeout=sys.argv[3])
        print("AURORA_PUSH " + json.dumps({"ref": r.ref, "url": r.url, "version": r.version_number, "error": r.error}))
    elif command == "status":
        r = api.kernels_status(sys.argv[2])
        print(json.dumps({"status": str(r.status).split(".")[-1].lower(), "failure": r.failure_message}))
    elif command == "cancel":
        # The stream endpoint resolves a pinned kernel version to its exact session.
        from kagglesdk.kernels.types.kernels_api_service import ApiGetKernelSessionLogsStreamRequest, ApiCancelKernelSessionRequest
        owner, slug, version = api.parse_kernel_string(sys.argv[2])
        request = ApiGetKernelSessionLogsStreamRequest()
        request.user_name, request.kernel_slug = owner, slug
        request.version_label = version or ""
        request.wait_for_logs_url_seconds = 1
        with api.build_kaggle_client() as client:
            response = client.kernels.kernels_api_client.get_kernel_session_logs_stream(request)
            session_id = getattr(response, "kernel_session_id", 0)
            if not session_id:
                raise RuntimeError("Session introuvable : arrêter cette version depuis Kaggle")
            cancel = ApiCancelKernelSessionRequest()
            cancel.kernel_session_id = session_id
            answer = client.kernels.kernels_api_client.cancel_kernel_session(cancel)
            print(json.dumps({"error": answer.error_message}))


if __name__ == "__main__":
    main()
