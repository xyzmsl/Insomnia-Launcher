import threading


def start_tracking(store, game_id, process, on_stop=None):
    if process is None:
        store.touch(game_id)
        return None
    session_id = store.start_session(game_id)

    def wait_and_close():
        try:
            process.wait()
        finally:
            store.close_session(session_id, tracked=True)
            if on_stop:
                on_stop()

    threading.Thread(target=wait_and_close, daemon=True).start()
    return session_id