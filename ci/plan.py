"""A single source of truth for expected E2E cases and their report rows."""
from __future__ import annotations
from ci.common import matrix_config, version_tuple

def plan(c=None):
    c = c or matrix_config()
    rows = []
    def add(suite, py, db, auth, profile="-", status="NOT_RUN", reason="", **kwargs):
        key = f"{suite}|{profile}|py{py}|mysql{db}|{auth}"
        rows.append(dict(id=key, suite=suite, python=py, django=profile, mysql=db,
                         auth=auth, status=status, reason=reason, **kwargs))
    for py in c["python"]:
        for db in c["mysql"]:
            for auth in c["auth"]:
                add("driver", py, db["version"], auth)
    for profile in c["django"]:
        for db in c["mysql"]:
            supported = version_tuple(db["version"]) >= version_tuple(profile["min_mysql"])
            for auth in c["auth"]:
                add("orm", profile["python"], db["version"], auth, profile["id"],
                    status="NOT_RUN" if supported else "EXCLUDED",
                    reason="" if supported else f"Django {profile['version']} requires MySQL >= {profile['min_mysql']}")
                if supported and profile["runtime"] and db["version"] in c["runtime_mysql"]:
                    for mode in ("wsgi", "asgi", "celery"):
                        add(mode, profile["python"], db["version"], auth, profile["id"])
    for db in c["runtime_mysql"]:
        for auth in c["auth"]:
            add("isolation", "3.12", db, auth)
            for distro in c["distros"]:
                add("distro", distro["python"], db, auth, distro=distro["id"], profile=distro["id"])
    assert len({r["id"] for r in rows}) == len(rows)
    return rows

if __name__ == "__main__":
    import json
    print(json.dumps(plan(), ensure_ascii=False, indent=2))
