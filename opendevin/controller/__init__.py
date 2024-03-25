import asyncio
from typing import List, Callable, Tuple

from opendevin.state import State
from opendevin.agent import Agent
from opendevin.action import (
    Action,
    NullAction,
    FileReadAction,
    FileWriteAction,
    AgentFinishAction,
)
from opendevin.observation import (
    Observation,
    NullObservation
)


from .command_manager import CommandManager


class AgentController:
    def __init__(
        self,
        agent: Agent,
        workdir: str,
        max_iterations: int = 100,
        callbacks: List[Callable] = [],
    ):
        self.agent = agent
        self.max_iterations = max_iterations
        self.workdir = workdir
        self.command_manager = CommandManager(workdir)
        self.callbacks = callbacks
        self.state_updated_info: List[Tuple[Action, Observation]] = []

    def get_current_state(self) -> State:
        # update observations & actions
        state = State(
            background_commands_obs=self.command_manager.get_background_obs(),
            updated_info=self.state_updated_info,
        )
        self.state_updated_info = []
        return state

    def add_observation(self, observation: Observation):
        self.state_updated_info.append((NullAction(), observation))

    async def start_loop(self, task_instruction: str):
        finished = False
        self.agent.instruction = task_instruction
        for i in range(self.max_iterations):
            try:
                finished = await self.step(i)
            except Exception as e:
                print("Error in loop", e, flush=True)
                break
            if finished:
                break
        if not finished:
            print("Exited before finishing", flush=True)

    async def step(self, i: int):
        print("STEP", i, flush=True)

        state: State = self.get_current_state()
        action: Action = self.agent.step(state)

        print("ACTION", action, flush=True)
        await self._run_callbacks(action)

        if isinstance(action, AgentFinishAction):
            print("FINISHED", flush=True)
            return True
        if isinstance(action, (FileReadAction, FileWriteAction)):
            action_cls = action.__class__
            _kwargs = action.__dict__
            _kwargs["base_path"] = self.workdir
            action = action_cls(**_kwargs)
            print(action, flush=True)
        print("---", flush=True)
        if action.executable:
            observation: Observation = action.run(self)
        else:
            observation = NullObservation("")
        print("OBSERVATION", observation, flush=True)
        self.state_updated_info.append((action, observation))

        print(observation, flush=True)
        await self._run_callbacks(observation)

        print("==============", flush=True)

    async def _run_callbacks(self, event):
        if event is None:
            return
        for callback in self.callbacks:
            idx = self.callbacks.index(callback)
            try:
                callback(event)
            except Exception as e:
                print("Callback error:" + str(idx), e, flush=True)
                pass
        await asyncio.sleep(0.001) # Give back control for a tick, so we can await in callbacks