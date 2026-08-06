import argparse
import json
import os

import psycopg2
from psycopg2.extensions import parse_dsn
from psycopg2.extras import RealDictCursor


IMPLEMENTATION_CODE = "long-term-memory-service-v1"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    dsn = os.environ["LOCAL_GENB_POSTGRES_DSN"]
    host = parse_dsn(dsn).get("host", "localhost")
    if host not in {"localhost", "127.0.0.1", "::1"}:
        raise RuntimeError("binding switch only accepts local PostgreSQL")

    with psycopg2.connect(dsn) as connection:
        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                "SELECT id FROM bank_agent_db.core_components WHERE component_code=%s",
                ("LONG_TERM_MEMORY",),
            )
            component = cursor.fetchone()
            if component is None:
                raise RuntimeError("LONG_TERM_MEMORY component is missing")
            component_id = component["id"]
            before = snapshot(cursor, component_id)
            if args.apply:
                cursor.execute(
                    """
                    INSERT INTO bank_agent_db.component_implementations
                    (component_id,implementation_code,owner,runtime_type,invocation_adapter,
                     interface_version,base_url,health_url,status)
                    VALUES (%s,%s,%s,'HTTP','LONG_TERM_MEMORY_V1','1.0.0',%s,%s,'REGISTERED')
                    ON CONFLICT (component_id,implementation_code) DO UPDATE SET
                      owner=EXCLUDED.owner,
                      runtime_type=EXCLUDED.runtime_type,
                      invocation_adapter=EXCLUDED.invocation_adapter,
                      interface_version=EXCLUDED.interface_version,
                      base_url=EXCLUDED.base_url,
                      health_url=EXCLUDED.health_url,
                      status='REGISTERED'
                    RETURNING id
                    """,
                    (
                        component_id,
                        IMPLEMENTATION_CODE,
                        "GenB Core Components Team",
                        "http://127.0.0.1:18702",
                        "http://127.0.0.1:18702/health/ready",
                    ),
                )
                implementation_id = cursor.fetchone()["id"]
                cursor.execute(
                    """
                    UPDATE bank_agent_db.agent_component_bindings
                    SET implementation_id=%s, status='ENABLED'
                    WHERE component_id=%s
                    """,
                    (implementation_id, component_id),
                )
                switched_bindings = cursor.rowcount
                cursor.execute(
                    """
                    UPDATE bank_agent_db.component_implementations
                    SET status='DISABLED'
                    WHERE component_id=%s AND id<>%s AND status<>'DISABLED'
                    """,
                    (component_id, implementation_id),
                )
                disabled_implementations = cursor.rowcount
                connection.commit()
                after = snapshot(cursor, component_id)
            else:
                switched_bindings = 0
                disabled_implementations = 0
                after = before

    print(
        json.dumps(
            {
                "mode": "APPLY" if args.apply else "DRY_RUN",
                "before": before,
                "after": after,
                "switchedBindings": switched_bindings,
                "disabledImplementations": disabled_implementations,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )


def snapshot(cursor, component_id: int) -> dict[str, object]:
    cursor.execute(
        """
        SELECT implementation_code,status,invocation_adapter,base_url
        FROM bank_agent_db.component_implementations
        WHERE component_id=%s ORDER BY id
        """,
        (component_id,),
    )
    implementations = [dict(row) for row in cursor.fetchall()]
    cursor.execute(
        """
        SELECT b.agent_id,i.implementation_code,b.status,b.config_version_id
        FROM bank_agent_db.agent_component_bindings b
        JOIN bank_agent_db.component_implementations i ON i.id=b.implementation_id
        WHERE b.component_id=%s ORDER BY b.agent_id
        """,
        (component_id,),
    )
    bindings = [dict(row) for row in cursor.fetchall()]
    return {"implementations": implementations, "bindings": bindings}


if __name__ == "__main__":
    main()
