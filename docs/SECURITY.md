# Sicherheitsdokumentation – Trevlix Trading Bot

Dieses Dokument beschreibt die Sicherheitsarchitektur und -richtlinien des Trevlix Trading Bots.

---

## 1. Authentifizierung

Trevlix verwendet eine mehrstufige Authentifizierung:

- **JWT-Tokens**: Nach erfolgreichem Login wird ein JSON Web Token ausgestellt, das nach **24 Stunden** automatisch ablaeuft. Tokens werden serverseitig mit dem `JWT_SECRET` signiert.
- **Passwort-Hashing**: Alle Passwoerter werden mit **bcrypt** gehasht, bevor sie in der Datenbank gespeichert werden. Klartext-Passwoerter werden zu keinem Zeitpunkt persistiert.
- **Zwei-Faktor-Authentifizierung (2FA/TOTP)**: Benutzer koennen zeitbasierte Einmalpasswoerter (TOTP) aktivieren, um den Login zusaetzlich abzusichern. Kompatibel mit gaengigen Authenticator-Apps (Google Authenticator, Authy, etc.).
- **Rate Limiting**: Alle Authentifizierungs-Endpunkte sind mit Rate Limiting geschuetzt, um Brute-Force-Angriffe zu verhindern.

---

## 2. Passwort-Richtlinien

Trevlix erzwingt strenge Passwort-Anforderungen:

- **Mindestlaenge**: 12 Zeichen
- **Grossbuchstaben**: Mindestens ein Grossbuchstabe erforderlich
- **Kleinbuchstaben**: Mindestens ein Kleinbuchstabe erforderlich
- **Ziffern**: Mindestens eine Ziffer erforderlich
- **Sonderzeichen**: Mindestens ein Sonderzeichen erforderlich

Zusaetzlich werden **15 schwache Muster** blockiert, darunter:

`password`, `admin`, `trevlix`, `123456`, `qwerty`, `letmein`, `welcome`, `monkey`, `master`, `dragon`, `login`, `abc123`, `passw0rd`, `shadow`, `trustno1`

Passwoerter, die eines dieser Muster enthalten (unabhaengig von Gross-/Kleinschreibung), werden abgelehnt.

---

## 3. API-Key Verschluesselung

Alle Exchange-API-Keys werden mit **Fernet-Verschluesselung** (AES-128-CBC + HMAC-SHA256) geschuetzt:

- Die Verschluesselung basiert auf der Umgebungsvariable `ENCRYPTION_KEY` (32-Byte URL-safe base64-kodierter Fernet-Key).
- API-Keys werden **verschluesselt in der Datenbank** gespeichert (encrypted at rest).
- Die Entschluesselung erfolgt **ausschliesslich im Arbeitsspeicher** und nur zum Zeitpunkt der Nutzung.
- Fehlt die `ENCRYPTION_KEY`, wird ein temporaerer Key generiert und eine Warnung ausgegeben – dieser Modus ist **nicht fuer den Produktionsbetrieb** geeignet.
- Thread-sichere Implementierung durch `threading.Lock`.

**Neuen Fernet-Key erzeugen:**

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

## 4. Netzwerk-Sicherheit

- **HTTPS**: Fuer den Produktionsbetrieb wird dringend empfohlen, ausschliesslich HTTPS zu verwenden. Die mitgelieferte Nginx-Konfiguration unter `docker/` unterstuetzt SSL/TLS-Terminierung.
- **CORS-Konfiguration**: Cross-Origin-Anfragen werden serverseitig konfiguriert und auf zugelassene Urspruenge beschraenkt.
- **Rate Limiting pro Endpunkt**: Jeder Endpunkt verfuegt ueber individuelle Rate Limits, um Missbrauch und DDoS-Angriffe abzumildern.

---

## 5. Datenbank-Sicherheit

- **Parametrisierte Abfragen**: Alle SQL-Abfragen verwenden ausschliesslich parametrisierte Queries. String-Interpolation in SQL-Statements ist strengstens untersagt, um SQL-Injection zu verhindern.
- **Connection Pooling**: Die Datenbankverbindungen werden ueber einen Thread-sicheren Connection Pool (`services/db_pool.py`) verwaltet.
- **Pool-Erschoepfungswarnungen**: Bei drohender Erschoepfung des Connection Pools werden Warnungen protokolliert, um Verfuegbarkeitsprobleme fruehzeitig zu erkennen.

---

## 6. Geschuetzte Konfiguration

Sensible Konfigurationsfelder werden durch ein `_PROTECTED_KEYS`-Frozenset geschuetzt. Diese Felder koennen **nicht ueber die API veraendert** werden:

- `admin_password`
- `jwt_secret`
- `secret_key`
- `encryption_key`
- `mysql_host`
- `mysql_user`
- `mysql_password`
- `mysql_database`
- weitere sicherheitsrelevante Felder

Aenderungen an diesen Werten erfordern direkten Zugriff auf die Umgebungsvariablen und einen Neustart der Anwendung.

---

## 7. Umgebungsvariablen (Environment Variables)

Geheimnisse duerfen **niemals** im Quellcode hartcodiert werden. Alle sensiblen Werte werden ueber Umgebungsvariablen bereitgestellt.

**Mindestanforderungen:**

| Variable | Anforderung |
|---|---|
| `JWT_SECRET` | Mindestens 32 hexadezimale Zeichen |
| `SECRET_KEY` | Mindestens 32 hexadezimale Zeichen |
| `ENCRYPTION_KEY` | 44 base64url-kodierte Zeichen (Fernet-Key) |
| `ADMIN_PASSWORD` | Mindestens 12 Zeichen, Gross-/Kleinbuchstaben, Ziffern, Sonderzeichen |

**Schluessel generieren:**

```bash
# JWT_SECRET oder SECRET_KEY erzeugen
python -c "import secrets; print(secrets.token_hex(32))"

# ENCRYPTION_KEY erzeugen
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Verwenden Sie die Datei `.env.example` als Vorlage und kopieren Sie diese nach `.env`, bevor Sie die Werte anpassen.

---

## 8. Schwachstellen melden (Vulnerability Reporting)

- **Oeffentliche Fehler**: Bitte melden Sie nicht-sicherheitskritische Fehler ueber [GitHub Issues](https://github.com/trevlix/trevlix/issues).
- **Sicherheitskritische Schwachstellen**: Bitte senden Sie sensible Sicherheitsberichte **nicht** ueber oeffentliche Issues. Nutzen Sie stattdessen eine direkte E-Mail an das Trevlix-Sicherheitsteam: **security@trevlix.com**

Wir bemuehen uns, Sicherheitsmeldungen innerhalb von 48 Stunden zu bestätigen und zeitnah zu beheben.
