from portal.routes import auth, board, chat, meta, rbac, requests, users

BLUEPRINTS = [meta.bp, auth.bp, users.bp, rbac.bp, requests.bp, chat.bp, board.bp]
