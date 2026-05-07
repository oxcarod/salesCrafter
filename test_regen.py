"""
Debug completo del flujo guardar → regenerar con Playwright.
Usa un marker ÚNICO para saber exactamente qué se guardó.
"""
import json, subprocess, sys

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Install: pip install playwright && playwright install chromium")
    sys.exit(1)

BASE_URL = "http://localhost:8789"
PLACE_ID = "ChIJwyzO_QX_0YURXcI28Js0Dbg"
BLOCK_ID = "hook_dinero_ChIJwyzO_QX_0YURXcI28Js0Dbg"

# Marker único que NUNCA va a estar en el template original
MARKER = "XYZ_UNIQUE_MARKER_12345_XYZ"

def api_delete(path):
    r = subprocess.run(["curl", "-s", "-X", "DELETE", f"{BASE_URL}{path}"], capture_output=True, text=True)
    return json.loads(r.stdout)

def api_get(path):
    r = subprocess.run(["curl", "-s", f"{BASE_URL}{path}"], capture_output=True, text=True)
    return json.loads(r.stdout)

def api_post(path, body):
    r = subprocess.run(["curl", "-s", "-X", "POST", f"{BASE_URL}{path}",
                        "-H", "Content-Type: application/json",
                        "-d", json.dumps(body)], capture_output=True, text=True)
    return json.loads(r.stdout)

def read_block_from_disk():
    """Leer el archivo JSON directamente del disco para evitar cache de API."""
    path = f"/Users/stark/projects/salesCrafter/blocks/{PLACE_ID}/{BLOCK_ID}.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def run():
    # Limpiar y generar bloque fresco
    api_delete(f"/api/prospect/{PLACE_ID}/bloque/eliminar/{BLOCK_ID}")
    r = api_post(f"/api/prospect/{PLACE_ID}/bloque/generar", {"tipo": "hook_dinero", "fuentes": None, "nombre": ""})
    assert r.get('status') == 'ok', f"Generación falló: {r}"
    orig = r['bloque']
    print(f"Block original — v{orig['metadata']['version']}")
    print(f"  prompt_custom[:80]: {repr(orig['prompt_custom'][:80])}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        console_logs = []
        def on_console(m):
            txt = f"[{m.type}] {m.text}"
            console_logs.append(txt)
            if 'DEBUG' in m.text or 'REGEN' in m.text or 'error' in m.text.lower():
                print(f"  PAGE: {txt}")
        page.on("console", on_console)

        print("\n=== Abrir editor ===")
        page.goto(f"{BASE_URL}/editor")
        page.wait_for_timeout(2000)

        print("=== Seleccionar prospecto ===")
        page.locator("#prospect-input").click()
        page.locator("#prospect-input").fill("Hospital")
        page.wait_for_timeout(600)
        page.locator(".prospect-item").first.click()
        page.wait_for_timeout(2000)

        print("=== Abrir hook_dinero ===")
        page.locator(".bloque-card").first.click()
        page.wait_for_timeout(1000)

        # Leer prompt actual
        ta = page.locator("#bloque-prompt-usado")
        actual = ta.input_value()
        print(f"  Textarea actual[:80]: {repr(actual[:80])}")
        assert len(actual) > 10, "Textarea vacío!"

        print(f"\n=== Editar textarea con marker UNICO ===")
        nuevo = actual.rstrip() + f"\n\n{MARKER}\n"
        ta.fill(nuevo)
        page.wait_for_timeout(300)
        verify = ta.input_value()
        print(f"  Verificado textarea: {MARKER in verify}")
        assert MARKER in verify, f"NO se pudo escribir en textarea!"

        print("\n=== Hacer clic en Guardar ===")
        page.locator("#btn-guardar").click()
        page.wait_for_timeout(3000)

        # Verificar en disco
        disk1 = read_block_from_disk()
        pc1 = disk1.get('prompt_custom', '')
        pu1 = disk1.get('prompt_usado', '')
        print(f"\n  Block en DISCO — version: {disk1['metadata']['version']}")
        print(f"  prompt_custom contiene marker: {MARKER in pc1}")
        print(f"  prompt_usado contiene marker: {MARKER in pu1}")
        print(f"  prompt_custom[:100]: {repr(pc1[:100])}")

        # Verificar textarea después de guardar
        ta_val = ta.input_value()
        print(f"  Textarea post-guardar[:80]: {repr(ta_val[:80])}")

        if not (MARKER in pc1):
            print("\n!!! ERROR: prompt_custom en DISCO NO tiene el marker!")
            print("  Esto significa que guardar() NO está escribiendo el texto correcto.")
            browser.close()
            return

        print("\n=== Hacer clic en Regenerar ===")
        # Diagnóstico: ejecutar fetch manualmente desde la página
        result = page.evaluate("""async () => {
            const bloque_id = selectedBloque ? selectedBloque.id : 'NO_ID';
            const prompt_val = document.getElementById('bloque-prompt-usado').value;
            const sources = getSelectedFuentes();
            console.log('MANUAL_FETCH bloque_id:', bloque_id);
            console.log('MANUAL_FETCH prompt_has_marker:', prompt_val.includes('XYZ_UNIQUE_MARKER_12345_XYZ'));
            console.log('MANUAL_FETCH currentPlaceId:', currentPlaceId);
            console.log('MANUAL_FETCH sources:', JSON.stringify(sources));
            try {
                const r = await fetch('/api/prospect/' + currentPlaceId + '/bloque/regenerar', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({bloque_id, fuentes: sources, prompt_extra: prompt_val})
                });
                const data = await r.json();
                console.log('MANUAL_FETCH status:', r.status, 'ok:', data.status, 'version:', data.bloque?.metadata?.version);
                console.log('MANUAL_FETCH prompt_custom[:80]:', (data.bloque?.prompt_custom || '').substring(0, 80));
                return JSON.stringify({status: r.status, ok: data.status, version: data.bloque?.metadata?.version, has_marker: (data.bloque?.prompt_custom || '').includes('XYZ_UNIQUE_MARKER_12345_XYZ')});
            } catch(e) {
                console.log('MANUAL_FETCH ERROR:', e.message);
                return JSON.stringify({error: e.message});
            }
        }""")
        print(f"  Fetch manual resultado: {result}")

        # Revisar logs de la página
        relevant = [l for l in console_logs if any(x in l for x in ['DEBUG','regenerar','error','ERROR','EXCEPTION','fetch'])]
        if relevant:
            print("  Page logs:")
            for l in relevant: print(f"    {l}")

        # Verificar en disco
        disk2 = read_block_from_disk()
        pc2 = disk2.get('prompt_custom', '')
        v2 = disk2['metadata']['version']
        print(f"\n  Block en DISCO post-regenerar — version: {v2}")
        print(f"  prompt_custom contiene marker: {MARKER in pc2}")
        print(f"  prompt_custom[:100]: {repr(pc2[:100])}")

        # Verificar en UI
        ta_post = ta.input_value()
        print(f"  Textarea post-regenerar[:80]: {repr(ta_post[:80])}")

        print("\n=== RESULTADO FINAL ===")
        print(f"  Guardado en disco con marker: {'OK' if MARKER in disk1.get('prompt_custom','') else 'FAIL'}")
        print(f"  Regeneración aumentó versión: {'OK' if v2 > disk1['metadata']['version'] else 'FAIL'}")
        print(f"  Block regenerado tiene marker: {'OK' if MARKER in disk2.get('prompt_custom','') else 'FAIL'}")
        print(f"  Textarea muestra marker: {'OK' if MARKER in ta_post else 'FAIL'}")

        browser.close()

if __name__ == "__main__":
    run()