#!/usr/bin/env python3
"""
Reproduce el bug exacto del usuario:
1. Abre bloque
2. Selecciona fuentes específicas (de MS Audit + reseñas)
3. Modifica el prompt (quitar el formato array de objetos label/valor)
4. Guarda
5. Regenerar
6. Verificar que el prompt siga siendo el personalizado del usuario

No se añade ningún marker artificial.
"""
import time
from playwright.sync_api import sync_playwright

SERVER = "http://127.0.0.1:8789"
PROSPECT_NAME = "Hospital Veterinario Delta"
PLACE_ID = "ChIJwyzO_QX_0YURXcI28Js0Dbg"

def run():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        errors = []

        # ── 1. Cargar editor ─────────────────────────────────────────────────
        page.goto(f"{SERVER}/editor")
        page.wait_for_load_state("networkidle")

        inp = page.locator("#prospect-input")
        inp.click()
        inp.fill(PROSPECT_NAME)
        page.wait_for_selector(".prospect-item", timeout=8000)
        page.locator(".prospect-item").first.click()
        time.sleep(3)
        print("[1] Editor listo")

        # ── 2. Abrir bloque ─────────────────────────────────────────────────
        page.wait_for_selector(".bloque-card", timeout=10000)
        first_card = page.locator(".bloque-card").first
        bloque_id = first_card.get_attribute("id").replace("bc-", "")
        first_card.click()
        page.wait_for_selector("#bloque-editor.visible", timeout=5000)
        time.sleep(0.5)

        prompt_original = page.locator("#bloque-prompt-usado").input_value()
        version_original = page.locator("#editor-version").inner_text()
        print(f"[2] Bloque abierto: {bloque_id}")
        print(f"    v{version_original}")
        print(f"    prompt[:100]: {prompt_original[:100]}")

        # ── 3. Modificar el prompt (QUITAR el formato de datos_concretos) ─────
        # El usuario quiere texto plano, NO el formato con arrays de objetos
        prompt_modificado = (
            "Eres un experto en análisis financiero de negocios de salud en México.\n"
            "Analiza los datos proporcionados y calcula cuánto dinero está dejando ir este negocio\n"
            "por no tener su presencia digital optimizada.\n\n"
            "Responde en texto plano, sin JSON, sin arrays de objetos. Solo párrafos claros.\n"
            "Tono directo con el dueño del negocio.\n"
        )
        page.locator("#bloque-prompt-usado").fill(prompt_modificado)
        page.locator("#bloque-prompt-usado").blur()
        time.sleep(0.5)
        print(f"[3] Prompt modificado por el usuario (length={len(prompt_modificado)})")
        print(f"    Nuevo prompt:\n{prompt_modificado[:150]}...")

        # ── 4. Guardar ─────────────────────────────────────────────────────
        page.locator("#btn-guardar").click()
        page.wait_for_timeout(2000)
        toast = page.locator("#toast").inner_text()
        print(f"[4] Guardar: '{toast}'")

        # ── 5. Regenerar ────────────────────────────────────────────────────
        page.locator("#btn-regenerar").click()
        page.wait_for_timeout(10000)
        toast_regen = page.locator("#toast").inner_text()
        prompt_after_regen = page.locator("#bloque-prompt-usado").input_value()
        version_after = page.locator("#editor-version").inner_text()
        print(f"[5] Tras regenerar:")
        print(f"    toast: '{toast_regen}'")
        print(f"    version: {version_after}")
        print(f"    prompt[:150]: {prompt_after_regen[:150]}")

        # ── 6. ASSERT: el prompt personalizado debe seguir igual ─────────────
        # El texto "sin JSON, sin arrays de objetos" es lo que identifica que
        # el usuario PERSONALIZÓ el prompt y no lo copió del template original
        marker_text = "sin JSON, sin arrays de objetos"
        if marker_text not in prompt_after_regen:
            errors.append(f"FAIL: el prompt personalizado se PIERDE tras regenerar")
            errors.append(f"  Se esperaba: '{marker_text}'")
            errors.append(f"  Prompt resultante[:200]: {prompt_after_regen[:200]}")
        else:
            print(f"    ✓ El texto personalizado del usuario sobrevive")

        # También verificar que NO se reinsertó el dato_concretos original
        if "datos_concretos" in prompt_after_regen and "array" in prompt_after_regen:
            errors.append(f"FAIL: se reinsertó el formato original de datos_concretos")
            errors.append(f"  prompt[:200]: {prompt_after_regen[:200]}")
        else:
            print(f"    ✓ El formato original (datos_concretos + array) NO reaparece")

        # ── 7. Recargar página y reabrir para verificar persistencia ───────────
        page.reload()
        page.wait_for_load_state("networkidle")
        time.sleep(1)

        inp2 = page.locator("#prospect-input")
        inp2.click()
        inp2.fill(PROSPECT_NAME)
        page.wait_for_selector(".prospect-item", timeout=8000)
        page.locator(".prospect-item").first.click()
        time.sleep(2)

        page.wait_for_selector(".bloque-card", timeout=10000)
        page.locator(f"#bc-{bloque_id}").click()
        page.wait_for_selector("#bloque-editor.visible", timeout=5000)
        time.sleep(0.5)

        prompt_final = page.locator("#bloque-prompt-usado").input_value()
        print(f"\n[7] Prompt tras recarga:")
        print(f"    has marker_text: {marker_text in prompt_final}")
        print(f"    prompt[:150]: {prompt_final[:150]}")

        if marker_text not in prompt_final:
            errors.append(f"FAIL: prompt se PIERDE tras recarga de pagina")
        else:
            print(f"    ✓ Marker persiste tras recarga")

        # ── Resultado ──────────────────────────────────────────────────────
        print("\n" + "="*50)
        if errors:
            print("RESULTADO: HAY ERRORES (bug encontrado)")
            for e in errors:
                print("  " + e)
        else:
            print("RESULTADO: TODO OK — no hay bug")

        browser.close()
        return len(errors) == 0

if __name__ == "__main__":
    ok = run()
    exit(0 if ok else 1)
