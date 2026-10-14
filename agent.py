# This file is part of Prometheus
# https://inl.gov/super-intelligence/prometheus/
#
# Copyright 2026 Battelle Energy Alliance, LLC
# All rights reserved, see NOTICE.txt for full restrictions
# https://github.com/idaholab/prometheus_core/blob/main/NOTICE.txt
#
# Licensed under the MIT License, please see LICENSE for details
# https://github.com/idaholab/prometheus_core/blob/main/LICENSE
#
# SPDX-License-Identifier: MIT

"""
Gnome Agent Agent.

Fix this later

This is a Prometheus specialist agent.  Subclass PrometheusAgent and implement
`_execute` — the base class handles the HTTP server, authentication, agent-card
serving, and registry registration for you.
"""

import logging
from typing import Any
import pandas as pd

import re
import io
import pandas as pd
import matplotlib
import csv
import os

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from prometheus_api import load_prompt  # noqa: F401 - used by the LLM pattern below
from prometheus_api.agent import EventQueue, PrometheusAgent, RequestContext
from prometheus_api.llm_client import LLMConfig

# Read secrets and configuration from environment variables.
# Never hard-code API keys or URLs here.
# Example (add `import os` to the imports above):
#   MY_API_KEY = os.getenv("MY_API_KEY")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class GnomeAgentAgent(PrometheusAgent):
    """Gnome Agent Agent."""

    # Optional: register agent-owned HTTP endpoints in __init__.
    #
    # def __init__(self, *args: Any, **kwargs: Any) -> None:
    #     super().__init__(*args, **kwargs)
    #     self.add_http_endpoint(
    #         "/api/preview/{artifact_id}",
    #         self.preview_artifact,
    #         methods=["GET"],
    #         endpoint_id="artifact_preview",
    #         purpose="artifact",
    #         description="Return preview metadata for one artifact.",
    #         content_types=["application/json"],
    #     )
    #     self.add_static_endpoint(
    #         "/viewer",
    #         "viewer-assets",
    #         endpoint_id="viewer_assets",
    #         purpose="viewer_plugin",
    #         description="Serve viewer plugin JavaScript and CSS.",
    #         content_types=["text/javascript", "text/css"],
    #     )
    #
    # async def preview_artifact(self, request):
    #     from starlette.responses import JSONResponse
    #
    #     return JSONResponse({"artifact_id": request.path_params["artifact_id"]})


    async def _execute(
        self,
        params: dict[str, Any],
        context: RequestContext,
        event_queue: EventQueue,
    ) -> dict[str, Any]:
        """Process one request.

        Args:
            params: Parameters from the caller's JSON payload, plus ``skill_id``
                from the message metadata (the skill the orchestrator selected).
            context: The A2A request context.  Use ``context.context_id`` as a
                stable key for per-conversation state.
            event_queue: Pass to the ``send_*`` helpers to emit progress updates
                and artifacts.

        Returns:
            A plain ``dict``.  The base class wraps it as the final ``completed``
            task status automatically — do not enqueue that event yourself.
        """
        # ------------------------------------------------------------------
        # 1. Read inputs from params.  These keys must match the properties
        #    declared in agent_card.json's inputSchema.
        # ------------------------------------------------------------------
        input_data = params.get("input_data")

        if not input_data:
            return {"status": "error", "error": "input_data is required"}

        # ------------------------------------------------------------------
        # 2. Send optional progress updates so the UI stays responsive.
        #    The base class sends the initial "working" update automatically;
        #    call this only when you want intermediate messages.
        # ------------------------------------------------------------------
        await self.send_status_update(
            context=context,
            event_queue=event_queue,
            message="Processing your request…",
        )

        # ------------------------------------------------------------------
        # 3. Do your actual work here.  Replace this with real logic.
        # ------------------------------------------------------------------
        skill_id = str(params.get("skill_id")).strip()
        artifact_id = str(params.get("artifact_id")).strip()

        if not artifact_id:
            ...

        artifacts = (params.get("artifacts") if isinstance(params.get("artifacts"), list) else None)

        path = self.get_artifact_file_path(artifact_id, context=context, artifacts=artifacts)

        source_ref = self.resolve_artifact_reference(self._context_conversation_id(context), artifact_id)
        if not source_ref:
            return {
                "status": "error",
                "conversation_id": self._context_conversation_id(context),
                "message": f"Artifact '{artifact_id}' was not found in this conversation.",
            }
        print(path)
        if skill_id == 'markdown_to_csv':
            markdown_text = await self.read_in_markdown(path_or_markdown=path)
            list_of_tuples = await self.markdown_to_csv(markdown_text=markdown_text)
            return await self.send_to_deeplynx(context=context,
                                          event_queue=event_queue,
                                          message="Reading in markdown to create csv",
                                          dict_of_csv=list_of_tuples)
        if skill_id == 'plot_csv':
            return await ...
        return {"status": "Error", "error": "unknown skill"}

        # ------------------------------------------------------------------
        # 4. Return a plain dict.  Keep keys consistent with the
        #    "output_format" you described in agent_card.json.
        # ------------------------------------------------------------------
        return result

    def read_in_markdown(self, path_or_markdown=None):
        """
        Read in the markdown file

        Args: 
            path_or_markdown (str) : string containing either the path to the markdown file or the markdown file itself

        Returns:
            markdown_text (str) : Return either the read in version of the path or the markdown file presented
        """
        if os.path.isfile(path_or_markdown):
            with open(path_or_markdown, "r") as f:
                return f.read()
        return path_or_markdown

    def markdown_to_csv(self, markdown_text):
        """
        Find every markdown table in the text and pair each with its nearest "Table N." caption.

        Args:
            markdown_text (str) : markdown text as a

        Returns:
            list_of_tuples (list) : a list of tuples; each tuple has a caption (str) and dataframe (df)
        """
        lines = markdown_text.splitlines()
        # Find the instances where we start a markdown table
        separator_re = re.compile(r"^\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?$")

        # Find the instance where Table is mentioned as the first word
        caption_re = re.compile(r"^\W*Table\b", re.IGNORECASE)

        # 1. Locate contiguous blocks of lines that form tables
        table_blocks = []  # list of (start_idx, end_idx_exclusive)
        i = 0
        while i < len(lines):
            if lines[i].strip().startswith("|"):
                start = i
                while i < len(lines) and lines[i].strip().startswith("|"):
                    i += 1
                table_blocks.append((start, i))
            else:
                i += 1

        # 2. For each table block, find caption + parse into a DataFrame
        list_of_tuples = []
        tab_num = 1
        for start, end in table_blocks:
            # Caption = nearest line above the table starting with "Table N."
            caption = ""
            for j in range(start - 1, -1, -1):
                line = lines[j].strip()

                if line.startswith("|"):
                    break  # hit another table before finding a caption
                match = caption_re.match(line)
                #print(match, line)
                if match:
                    caption_start_index = j
                    caption_end_index = start - 1
                    caption = "".join(lines[caption_start_index:caption_end_index])
                    break


            # Drop the markdown separator row (e.g. |---|---|), then strip leading/trailing pipes
            table_lines = [
                line.strip().strip("|")
                for line in lines[start:end]
                if not separator_re.match(line.strip())
            ]
            if not table_lines:
                continue

            table_text = "\n".join(table_lines)
            df = pd.read_table(
                io.StringIO(table_text), sep=r"\s*\|\s*", engine="python"
            )
            df.columns = [c.strip() for c in df.columns]
            list_of_tuples.append((caption,  df))
        return list_of_tuples

    def send_to_deeplynx(self, context, event_queue, message, list_of_tuples, base_path='./'):
        """
        Take the dictionary of captions and csvs and send this to DeepLynx
        Args:
            list_of_tuples (list): which takes the form
            (
                caption (str)                : string containing the table captions
                dataframe (pandas.DataFrame) : pandas data frame containing the table associated with the caption
            )
        Returns:
            results (list) : list of table_id's created in deeplynx for each caption-df pair
        """
        tab_num = 0
        results = []
        for caption, df in list_of_tuples:
            rows = df.values.tolist()
            file_path = os.path.join(base_path, f'table_{tab_num}.csv')

            # Create a DeepLynx artifact which contains the
            table_id = self.send_deeplynx_artifact(
                context,
                event_queue,
                name=f'Table {tab_num}',
                file_path=file_path,
                description=f'Table file for Table{tab_num}',
                catalog_artifact=True,
            )
            results.append(table_id)
            tab_num += 1
        return results

    def plot_table(context, event_queue, message, text_path):
        """
        Get the artefact and plot it as another artefact.  This is a placeholder for your actual plotting logic.
        """
        path = self.get_artifact_file_path(
            params["table_artifact_id"],
            context=context,
            artifacts=params.get("artifacts"),
        )

        # table_id = await self.send_json_artifact(
        #     context, event_queue, payload, name="table", catalog_artifact=True
        # )

        # Placeholder: Use LLM to figure out which columns to plot
        x_col_raw = params["x_column"]
        if not x_col_raw:
            return {"status": "error", "error": "x_column is required"}
        y_col_raw = params["y_column"]
        if not y_col_raw:
            return {"status": "error", "error": "y_column is required"}
        
        # cfg = LLMConfig.from_env()   # profile from .env
        # if cfg.proxy_url:            # only the platform proxy
        #     cfg = cfg.with_api_key(os.getenv("LITELLM_MASTER_KEY"))

        # async with self.llm_client(context, config=cfg) as llm:
        #     r = await llm.small(
        #         f"Which caption matches '{desc}'? {captions}")
        # answer = r.text

        # For now, just plot the first two columns
        png_name = plot_csv_xy(self, path, 0, 1, "plot_table.png")

        ref = self.send_deeplynx_artifact(
            context=context,
            event_queue=event_queue,
            file_path=png,
            name=png_name,
            description="plot of csv",
            storage_config=ConnectionConfig.from_env(),
            mime_type="image/png",
        )
        return {"status": "success", "artifact_id": ref.artifact_id}

    def plot_csv_xy(self,file_path, x_col=0, y_col=1, png_file="plot_table.png"):
        """
        Plot two columns of a CSV file and save the chart as a PNG.
        csv_file : path to the CSV file (first row must be a header)
        x_col    : x column, as a header name (str) or zero-based index (int)
        y_col    : y column, as a header name (str) or zero-based index (int)
        png_file : output PNG file name
        Returns  : the PNG file name
        """

        x, y = [], []

        # Read the CSV ("utf-8-sig" strips the BOM that Excel sometimes adds)
        with open(file_path, newline="", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            header = [h.strip() for h in next(reader)]

            # Convert column names to indices; integers are used as-is
            xi = header.index(x_col) if isinstance(x_col, str) else x_col
            yi = header.index(y_col) if isinstance(y_col, str) else y_col

            # Collect numeric values, skipping blank or invalid rows
            for row in reader:
                try:
                    x.append(float(row[xi]))
                    y.append(float(row[yi]))
                except (ValueError, IndexError):
                    continue

        # Plot the data and label the axes with the column headers
        plt.plot(x, y)
        plt.xlabel(header[xi])
        plt.ylabel(header[yi])
        plt.title(f"{header[yi]} vs {header[xi]}")
        plt.grid(True)

        # Save to PNG, then close the figure to free memory
        plt.savefig(png_file, dpi=150, bbox_inches="tight")
        plt.close()

        return png_file

    # ----------------------------------------------------------------------
    # PATTERNS — uncomment and adapt as needed.
    # ----------------------------------------------------------------------
    #
    # Calling an LLM through the platform's LiteLLM gateway:
    #
    #     system_prompt = load_prompt("system_prompt.txt").format(input_data=input_data)
    #     async with self.llm_client(context) as llm:
    #         response = await llm.medium(system_prompt)
    #     return {"status": "success", "summary": response.text}
    #
    # Dispatching when agent_card.json declares more than one skill:
    #
    #     handler = {
    #         "skill_a": self._handle_a,
    #         "skill_b": self._handle_b,
    #     }.get(params.get("skill_id"))
    #     if handler is None:
    #         return {"status": "error", "error": f"Unknown skill: {params.get('skill_id')}"}
    #     return await handler(params, context, event_queue)
    #
    # Persisting per-conversation state across turns (Redis-backed, with an
    # in-memory fallback for local development):
    #
    #     state = self.load_context_state(str(context.context_id))
    #     state["count"] = state.get("count", 0) + 1
    #     self.save_context_state(str(context.context_id), state)
    #
    # See TUTORIAL.md ("Advanced topics") for emitting artifacts, asking the
    # user for missing inputs (INPUT_REQUIRED), and DeepLynx file storage.


if __name__ == "__main__":
    agent = GnomeAgentAgent(agent_name="Gnome Agent Agent")
    agent.run()
