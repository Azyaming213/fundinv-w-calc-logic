import unittest
from unittest.mock import patch

import main
from jobs import migration_job


class MigrationStartupTests(unittest.IsolatedAsyncioTestCase):
    async def test_migrations_run_even_when_scheduler_is_disabled(self):
        with (
            patch.object(main.settings, "ENVIRONMENT", "development"),
            patch.object(main.settings, "ENABLE_SCHEDULER", "false"),
            patch("main.run_pending_migrations") as run_migrations,
            patch("main.sync_role_claims"),
        ):
            async with main.lifespan(main.app):
                pass

        run_migrations.assert_called_once_with()

    def test_migration_failure_prevents_startup(self):
        with (
            patch.object(migration_job.settings, "AUTO_MIGRATE", "true"),
            patch("jobs.migration_job.command.upgrade", side_effect=RuntimeError("migration failed")),
        ):
            with self.assertRaisesRegex(RuntimeError, "migration failed"):
                migration_job.run_pending_migrations()


if __name__ == "__main__":
    unittest.main()
