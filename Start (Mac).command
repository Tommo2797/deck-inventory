#!/bin/bash
# Deck Inventory - avvio con doppio clic su Mac.
# Tutto ciò che viene scaricato (uv, Python, librerie, eventuale browser) resta
# in .app/runtime/ dentro questa cartella.
#
# Variabile per test automatici: DECK_INVENTORY_NO_DIALOG=1 salta i dialog del
# launcher (prima installazione ed errori, che sono modali) e scrive i messaggi
# sul terminale. I dialog di Deck Inventory stesso (Python) non cambiano.

UV_VERSION="0.13.1"

ROOT="$(cd "$(dirname "$0")" && pwd -P)" || exit 1
cd "$ROOT" || exit 1

RT="$ROOT/.app/runtime"
SRC="$ROOT/.app/src"
UV="$RT/uv/uv"
STATE_FILE="$RT/install-state.txt"

export UV_CACHE_DIR="$RT/uv-cache"
export UV_PYTHON_INSTALL_DIR="$RT/python"
export UV_PROJECT_ENVIRONMENT="$RT/venv"
export PLAYWRIGHT_BROWSERS_PATH="$RT/browsers"
export UV_PYTHON_PREFERENCE="only-managed"
export UV_NO_CONFIG=1
# pyproject ha package = false: il pacchetto si importa da .app/src.
export PYTHONPATH="$SRC"
unset VIRTUAL_ENV

# Finestra del Terminale: ridotta all'avvio, chiusa alla fine. La finestra si
# riconosce dal tty (il titolo dipende dalle preferenze del Terminale).
# Solo se la finestra ha un'unica scheda: se lo script è stato aperto come
# scheda in una finestra dell'utente, la finestra non si tocca.
# Se non riesce, pazienza: nient'altro dipende da questo.
MY_TTY="$(tty 2>/dev/null)"

in_terminal() { [ "$TERM_PROGRAM" = "Apple_Terminal" ] && [ "${MY_TTY#/dev/}" != "$MY_TTY" ]; }

terminal_window() {
    # $1 = azione AppleScript sulla finestra w, es. "close w"
    osascript \
        -e 'on run argv' \
        -e 'tell application "Terminal"' \
        -e 'repeat with w in windows' \
        -e 'if (tty of tabs of w) contains (item 1 of argv) then' \
        -e 'if (count of tabs of w) is 1 then' \
        -e "$1" \
        -e 'end if' \
        -e 'exit repeat' \
        -e 'end if' \
        -e 'end repeat' \
        -e 'end tell' \
        -e 'end run' \
        "$MY_TTY" >/dev/null 2>&1
}

if in_terminal; then
    terminal_window "set miniaturized of w to true"
fi

finish() {
    if in_terminal; then
        # In background: chiude la finestra dopo che lo script è uscito.
        ( sleep 1; terminal_window "close w" ) </dev/null >/dev/null 2>&1 &
        disown 2>/dev/null
    fi
    exit "$1"
}

dialog() {
    # $1 = testo, $2 = icona (note | stop)
    if [ "$DECK_INVENTORY_NO_DIALOG" = "1" ]; then
        echo "[dialog] $1" >&2
        return
    fi
    local text="${1//\\/\\\\}"
    text="${text//\"/\\\"}"
    osascript -e "display dialog \"$text\" with title \"Deck Inventory\" buttons {\"OK\"} default button 1 with icon $2" >/dev/null 2>&1
}

case "$(uname -m)" in
    arm64) ARCH="arm64"; UV_TARGET="aarch64-apple-darwin" ;;
    *)     ARCH="x64";   UV_TARGET="x86_64-apple-darwin" ;;
esac
STATE="$ROOT|darwin-$ARCH"

# Guard: cartella spostata/copiata (venv con percorsi assoluti) o altra piattaforma.
if [ -f "$STATE_FILE" ]; then
    OLD_STATE="$(head -n 1 "$STATE_FILE")"
    if [ "${OLD_STATE##*|}" != "darwin-$ARCH" ]; then
        rm -rf "$RT/venv" "$RT/python" "$RT/uv" "$RT/browsers"
    elif [ "$OLD_STATE" != "$STATE" ] && ! [ "${OLD_STATE%|*}" -ef "$ROOT" ]; then
        # -ef: stessa cartella anche se il percorso è scritto diversamente
        # (es. "à" composta o scomposta: Finder e Terminale non sono coerenti).
        rm -rf "$RT/venv"
    fi
fi

if [ ! -x "$UV" ]; then
    dialog "Prima installazione: Deck Inventory scaricherà i componenti necessari dentro la sua cartella. Può richiedere qualche minuto. Al termine si aprirà la pagina." note
    DL="$RT/uv-download"
    rm -rf "$DL"
    mkdir -p "$DL" "$RT/uv"
    URL="https://github.com/astral-sh/uv/releases/download/$UV_VERSION/uv-$UV_TARGET.tar.gz"
    # Copia con nome temporaneo e poi mv (uv per ultimo): se si interrompe a metà
    # non resta un "uv" troncato che al prossimo avvio sembrerebbe installato.
    if ! curl -fL --retry 2 -o "$DL/uv.tar.gz" "$URL" \
        || ! tar -xzf "$DL/uv.tar.gz" -C "$DL" \
        || ! cp "$DL/uv-$UV_TARGET/uvx" "$RT/uv/uvx.part" \
        || ! cp "$DL/uv-$UV_TARGET/uv" "$RT/uv/uv.part" \
        || ! chmod +x "$RT/uv/uvx.part" "$RT/uv/uv.part" \
        || ! mv -f "$RT/uv/uvx.part" "$RT/uv/uvx" \
        || ! mv -f "$RT/uv/uv.part" "$UV"; then
        rm -rf "$DL" "$RT/uv"
        dialog "Non riesco a scaricare i componenti di Deck Inventory. Controlla la connessione a internet e riprova." stop
        finish 1
    fi
    rm -rf "$DL"
fi

if ! "$UV" sync --project "$SRC" --frozen --no-dev; then
    dialog "Installazione non riuscita, controlla la connessione e riprova." stop
    finish 1
fi
printf '%s\n' "$STATE" > "$STATE_FILE"

# Aggiornamento automatico (logica tutta in Python, che si aggiorna da sé).
# Non blocca mai l'avvio: il codice d'uscita si ignora.
export DECK_INVENTORY_LAUNCHER=1
export DECK_INVENTORY_UV="$UV"
"$UV" run --project "$SRC" --frozen --no-dev python -m deck_inventory.update "$ROOT"

# In caso di errore Deck Inventory ha già mostrato il suo messaggio.
"$UV" run --project "$SRC" --frozen --no-dev python -m deck_inventory "$ROOT"
finish $?
