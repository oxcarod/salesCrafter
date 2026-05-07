#!/usr/bin/env python3
"""
Test directo por API: verificar que prompt_custom se preserva tras regeneración.
"""
import json, subprocess, time, requests

SERVER = "http://127.0.0.1:8789"
PROSPECT_ID = "ChIJwyzO_QX_0YURXcI28Js0Dbg"
PLACE_ID = PROSPECT_ID
MARKER = "XYZ_TEST_MARKER_99999_MARKER"

def call(method, url, **kwargs):
    r = requests.request(method, url, timeout=60, **kwargs)
    print(f"  API {method} {url} → {r.status_code}")
    try:
        return r.json()
    except:
        print(f"  Raw: {r.text[:200]}")
        return {}

def save_modified_prompt(block_id):
    """Guarda un bloque con prompt personalizado que incluye MARKER."""
    bloque = call("GET", f"{SERVER}/api/prospect/{PLACE_ID}/bloque/{block_id}")["bloque"]
    print(f"\n[GET bloque] id={bloque['id']}")
    print(f"  prompt_usado[:80] = {bloque.get('prompt_usado','')[:80]}")
    print(f"  prompt_custom[:80] = {bloque.get('prompt_custom','')[:80]}")

    # Guardar con prompt modificado
    bloque["prompt_usado"] = bloque.get("prompt_usado","") + f"\n\n-- MODIFICADO POR TEST [{MARKER}] --\nSe agregaron instrucciones personalizadas."
    bloque["prompt_custom"] = bloque["prompt_usado"]
    bloque["metadata"] = bloque.get("metadata", {})
    bloque["metadata"]["usuario_edito"] = True

    resp = call("POST", f"{SERVER}/api/prospect/{PLACE_ID}/bloque/guardar",
               json=bloque)
    print(f"  guardar → {resp.get('status')}")

    # Verificar que se guardó bien
    bloque2 = call("GET", f"{SERVER}/api/prospect/{PLACE_ID}/bloque/{block_id}")["bloque"]
    has_marker = MARKER in (bloque2.get("prompt_usado","") + bloque2.get("prompt_custom",""))
    print(f"  POST-SAVE marker presente: {has_marker}")
    print(f"  prompt_usado[:80] = {bloque2.get('prompt_usado','')[:80]}")
    print(f"  prompt_custom[:80] = {bloque2.get('prompt_custom','')[:80]}")
    return has_marker

def regenerate_and_check(block_id, prompt_extra):
    """Llama al endpoint regenerar y retorna el bloque devuelto."""
    resp = call("POST", f"{SERVER}/api/prospect/{PLACE_ID}/bloque/regenerar",
                json={"bloque_id": block_id, "prompt_extra": prompt_extra})
    print(f"  regenerar → {resp.get('status')}, version={resp.get('bloque',{}).get('metadata',{}).get('version')}")
    return resp.get("bloque", {})

def main():
    print("=== TEST: prompt_custom se preserva tras regeneración ===\n")

    # 1. Obtener bloque
    bloques = call("GET", f"{SERVER}/api/prospect/{PLACE_ID}/bloques")["bloques"]
    print(f"Bloques disponibles: {[b['id'] for b in bloques]}")
    bloque_id = bloques[0]["id"]

    # 2. Guardar con prompt modificado
    marker_ok = save_modified_prompt(bloque_id)
    if not marker_ok:
        print("FAIL: el marker no se guardó en el bloque")
        exit(1)

    # 3. Leer el prompt que se mandaría al regenerate
    bloque_post = call("GET", f"{SERVER}/api/prospect/{PLACE_ID}/bloque/{bloque_id}")["bloque"]
    prompt_enviar = bloque_post.get("prompt_usado", "")
    prompt_enviar_display = prompt_enviar.split("--- DATOS ---")[0].strip()

    print(f"\n[3] Prompt que se envía a regenerate (sin DATOS):")
    print(f"    length={len(prompt_enviar_display)}")
    print(f"    contains marker: {MARKER in prompt_enviar_display}")
    print(f"    preview: {prompt_enviar_display[:100]}")

    # 4. Regenerar
    print(f"\n[4] Llamando regenerate con prompt_extra (length={len(prompt_enviar_display)})...")
    new_bloque = regenerate_and_check(bloque_id, prompt_enviar)

    # 5. Verificar qué tiene el nuevo bloque
    print(f"\n[5] Nuevo bloque devuelto por regenerate:")
    new_pu = new_bloque.get("prompt_usado", "")
    new_pc = new_bloque.get("prompt_custom", "")
    print(f"  prompt_usado[:100]   = {new_pu[:100]}")
    print(f"  prompt_custom[:100]  = {new_pc[:100]}")
    print(f"  prompt_usado contains MARKER: {MARKER in new_pu}")
    print(f"  prompt_custom contains MARKER: {MARKER in new_pc}")

    # 6. Re-leer el bloque desde el API para verificar persistencia
    print(f"\n[6] Re-leyendo bloque desde API...")
    bloque_reloaded = call("GET", f"{SERVER}/api/prospect/{PLACE_ID}/bloque/{bloque_id}")["bloque"]
    rp_pu = bloque_reloaded.get("prompt_usado", "")
    rp_pc = bloque_reloaded.get("prompt_custom", "")
    print(f"  prompt_usado contains MARKER: {MARKER in rp_pu}")
    print(f"  prompt_custom contains MARKER: {MARKER in rp_pc}")
    print(f"  prompt_usado[:100] = {rp_pu[:100]}")

    print("\n── RESULTADO ──")
    errors = []
    if not (MARKER in new_pu or MARKER in new_pc):
        errors.append("FAIL: el nuevo bloque NO tiene el marker en prompt_usado ni prompt_custom")
    if not (MARKER in rp_pu or MARKER in rp_pc):
        errors.append("FAIL: el bloque re-leído NO tiene el marker")

    if errors:
        for e in errors:
            print(e)
        exit(1)
    else:
        print("PASS: el prompt personalizado se preservó correctamente")
        exit(0)

if __name__ == "__main__":
    main()
