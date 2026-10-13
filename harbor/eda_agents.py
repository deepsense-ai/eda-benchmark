"""Harbor agent overrides for the EDA benchmark task images.

Used through Harbor's ``module:Class`` agent names; the Makefile puts ``harbor/`` on
PYTHONPATH and maps ``AGENT=antigravity-cli`` here.
"""

from harbor.agents.installed.antigravity_cli import AntigravityCli as _HarborAntigravityCli
from harbor.environments.base import BaseEnvironment


class AntigravityCli(_HarborAntigravityCli):
    """antigravity-cli that reuses the ``agy`` preinstalled in the base image.

    Harbor's install runs ``curl ... install.sh | bash`` under ``pipefail``. With ``agy``
    already present the script exits after its first lines, curl then fails writing to the
    closed pipe (exit 23) and the trial errors out. Skip the installer in that case.
    """

    async def install(self, environment: BaseEnvironment) -> None:
        check = await environment.exec(command="test -x $HOME/.local/bin/agy")
        if check.return_code != 0:
            await super().install(environment)
            return
        await self.exec_as_agent(environment, command="$HOME/.local/bin/agy --version")
