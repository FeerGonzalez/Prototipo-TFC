import uuid, json, re, pdfplumber
from datetime import datetime
from pyld import jsonld
from jose import jws
import sys
import requests

# -------------------------------
# Document Loader personalizado para JSON-LD
# -------------------------------
def requests_document_loader(url, options=None):
    r = requests.get(url)
    r.raise_for_status()
    return {
        "contextUrl": None,
        "documentUrl": url,
        "document": r.json()
    }

jsonld.set_document_loader(requests_document_loader)

# -------------------------------
# Extraer datos del PDF
# -------------------------------
def extract_fields(pdf_path):
    text = ""
    with pdfplumber.open(pdf_path) as doc:
        for p in doc.pages:
            page_text = p.extract_text()
            if page_text:
                text += page_text + "\n"

    m_nombre = re.search(r"CERTIFICA QUE:\s*([A-Za-zÁÉÍÓÚÑáéíóúñ\s]+),\s*DNI", text)
    m_dni = re.search(r"DNI:\s*(\d+)", text)
    m_curso = re.search(r"Curso\s*[“\"](.+?)[”\"]", text)

    return {
        "nombre": m_nombre.group(1).strip() if m_nombre else "",
        "dni": m_dni.group(1).strip() if m_dni else "",
        "programa": m_curso.group(1).strip() if m_curso else "Curso aprobado",
        "fecha_emision": ""
    }


# -------------------------------
# Mapear a estructura ELM / VC
# -------------------------------
def build_jsonld(datos):
    issuanceDate = datos.get("fecha_emision") or datetime.utcnow().date().isoformat()

    nombre = datos["nombre"]
    partes = nombre.split()
    given = partes[0]
    family = " ".join(partes[1:])

    credential = {
        "@context": [
            "https://www.w3.org/2018/credentials/v1",
            "https://schema.org/docs/jsonldcontext.json"
        ],
        "id": f"urn:uuid:{uuid.uuid4()}",
        "type": ["VerifiableCredential", "TrainingCertificate"],
        "issuer": {
            "id": "https://unrn.edu.ar",
            "name": "Universidad Nacional de Río Negro"
        },
        "issuanceDate": f"{issuanceDate}T00:00:00Z",
        "credentialSubject": {
            "id": f"did:example:{datos['dni']}",
            "givenName": given,
            "familyName": family,
            "dni": datos["dni"],
            "courseName": datos["programa"],
            "status": "Curso aprobado",
            "academicYear": "2025"
        }
    }
    return credential


# -------------------------------
# Normalizar JSON-LD y firmar (crear proof)
# -------------------------------
def canonicalize(jsonld_doc):
    normalized = jsonld.normalize(
        jsonld_doc,
        {'algorithm': 'URDNA2015', 'format': 'application/n-quads'}
    )
    return normalized


def sign_credential(credential, key='secret-demo-key'):
    normalized = canonicalize(credential)
    token = jws.sign(normalized.encode('utf-8'), key, algorithm='HS256')

    proof = {
        "type": "LinkedDataSignature",
        "created": credential["issuanceDate"],
        "proofPurpose": "assertionMethod",
        "verificationMethod": "https://unrn.edu.ar/keys/1",
        "jws": token
    }

    credential["proof"] = proof
    return credential


# -------------------------------
# Flujo Completo
# -------------------------------
if __name__ == "__main__":
    ruta_pdf = sys.argv[1] if len(sys.argv) > 1 else "ejemplo_certificado.pdf"

    print("Extrayendo datos del PDF...")
    datos = extract_fields(ruta_pdf)
    print("Datos extraídos:", datos)

    print("\nConstruyendo la credencial JSON-LD...")
    cred = build_jsonld(datos)

    print("\nFirmando la credencial...")
    cred_firmada = sign_credential(cred)

    with open("credencial_firmada.json", "w", encoding="utf-8") as f:
        json.dump(cred_firmada, f, ensure_ascii=False, indent=4)

    print("\n¡Proceso completo!")
    print("Archivo generado: credencial_firmada.json")
