#!/usr/bin/env python3
"""
Reproduce el flujo EXACTO del usuario SIN recarga de página:

1. Abre bloque
2. Modifica prompt (quitar array label/valor)
3. Guarda
4. Inmediatamente regenera (SIN recargar)
5. Verificar que el prompt siga siendo el personalizado
"""
import time
import requests
from playwright.sync_api import sync_playwright

SERVER = "http://127.0.0.1:8789"
PROSPECT_NAME = "Hospital Veterinario Delta"
PLACE_ID = "ChIJwyzO_QX_0YURXcI28Js0Dbg"

def run():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        errors = []

        # ── 1. Cargar editor y seleccionar prospecto ──────────────────────
        page.goto(f"{SERVER}/editor")
        page.wait_for_load_state("networkidle")
        inp = page.locator("#prospect-input")
        inp.click()
        inp.fill(PROSPECT_NAME)
        page.wait_for_selector(".prospect-item", timeout=8000)
        page.locator(".prospect-item").first.click()
        time.sleep(3)
        print("[1] Editor listo")

        # ── 2. Abrir bloque ─────────────────────────────────────────────
        page.wait_for_selector(".bloque-card", timeout=10000)
        first_card = page.locator(".bloque-card").first
        bloque_id = first_card.get_attribute("id").replace("bc-", "")
        first_card.click()
        page.wait_for_selector("#bloque-editor.visible", timeout=5000)
        time.sleep(0.5)

        prompt_original = page.locator("#bloque-prompt-usado").input_value()
        version_original = page.locator("#editor-version").inner_text()
        print(f"[2] Bloque: {bloque_id}, v{version_original}")
        print(f"    prompt orig[:100]: {prompt_original[:100]}")

        # ── 3. Modificar prompt (quitar formato label/valor) ────────────
        prompt_modificado = (
            "Eres un experto en analisis financiero de negocios de salud en Mexico.\n"
            "Responde en texto plano, sin JSON, sin arrays de objetos label/valor.\n"
            "Solo parrafos claros en espanol mexicano.\n"
        )
        page.locator("#bloque-prompt-usado").fill(prompt_modificado)
        page.locator("#bloque-prompt-usado").blur()
        time.sleep(0.3)
        print(f"[3] Prompt modificado (length={len(prompt_modificado)})")

        # ── 4. Guardar ────────────────────────────────────────────────
        page.locator("#btn-guardar").click()
        page.wait_for_timeout(2000)
        toast_save = page.locator("#toast").inner_text()
        print(f"[4] Guardar: '{toast_save}'")

        # ── 5. Regenerar INMEDIATAMENTE (sin recargar) ─────────────────
        prompt_antes_regen = page.locator("#bloque-prompt-usado").input_value()
        print(f"[5] Prompt ANTES de regenerar:")
        print(f"    length={len(prompt_antes_regen)}")
        print(f"    has 'sin JSON': {'sin JSON' in prompt_antes_regen}")
        print(f"    has 'datos_concretos': {'datos_concretos' in prompt_antes_regen}")
        print(f"    prompt[:100]: {prompt_antes_regen[:100]}")

        page.locator("#btn-regenerar").click()
        page.wait_for_timeout(10000)
        toast_regen = page.locator("#toast").inner_text()
        version_after = page.locator("#editor-version").inner_text()
        prompt_after_regen = page.locator("#bloque-prompt-usado").input_value()

        print(f"\n[5b] Tras regenerar:")
        print(f"    toast: '{toast_regen}'")
        print(f"    version: {version_after}")
        print(f"    has 'sin JSON': {'sin JSON' in prompt_after_regen}")
        print(f"    has 'datos_concretos': {'datos_concretos' in prompt_after_regen}")
        print(f"    prompt[:150]: {prompt_after_regen[:150]}")

        # ── 6. ASSERT ─────────────────────────────────────────────────
        marker = "sin JSON"
        if marker not in prompt_after_regen:
            errors.append(f"FAIL: texto personalizado 'sin JSON' se PIERDE tras regenerar")
            errors.append(f"  prompt[:200]: {prompt_after_regen[:200]}")
        else:
            print("    ✓ Texto personalizado sobrevive")

        if "datos_concretos" in prompt_after_regen:
            errors.append("FAIL: se reinsertó el formato 'datos_concretos' del template original")
        else:
            print("    ✓ Formato original NO reaparece")

        if version_original != version_after:
            print(f"    ✓ Version cambio: {version_original} -> {version_after}")
        else:
            errors.append("FAIL: la version NO cambio (no hubo regeneracion real)")

        # ── 7. Recargar y verificar persistencia ──────────────────────────
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
        print(f"\n[7] Tras recarga:")
        print(f"    has 'sin JSON': {'sin JSON' in prompt_final}")
        print(f"    prompt[:150]: {prompt_final[:150]}")

        if marker not in prompt_final:
            errors.append("FAIL: prompt se PIERDE tras recarga de pagina")
        else:
            print("    ✓ Texto persiste tras recarga")

        # ── Resultado ──────────────────────────────────────────────────
        print("\n" + "="*50)
        if errors:
            print("RESULTADO: BUG ENCONTRADO")
            for e in errors:
                print("  " + e)
        else:
            print("RESULTADO: TODO OK")

        browser.close()
        return len(errors) == 0

if __name__ == "__main__":
    ok = run()
    exit(0 if ok else 1)
