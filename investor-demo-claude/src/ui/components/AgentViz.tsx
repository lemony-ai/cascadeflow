import React from "react";
import { Box, Text } from "ink";
import Spinner from "ink-spinner";

export interface AgentNode {
  name: string;
  steps: AgentStep[];
  status: "pending" | "running" | "done";
}

export interface AgentStep {
  tool: string;
  route: "accepted" | "escalated" | "pending" | "running";
  result?: string;
}

interface AgentVizProps {
  agents: AgentNode[];
  progress: number;
}

export function AgentViz({ agents, progress }: AgentVizProps) {
  return (
    <Box flexDirection="column" borderStyle="single" borderColor="gray" paddingX={1}>
      <Text color="white" bold>
        Agent Orchestration
      </Text>
      <Box marginTop={1} flexDirection="column">
        {agents.map((agent) => (
          <Box key={agent.name} flexDirection="column" marginBottom={1}>
            <Box>
              {agent.status === "running" ? (
                <Text color="yellow">
                  <Spinner type="dots" />{" "}
                </Text>
              ) : agent.status === "done" ? (
                <Text color="green">{"\u2714"} </Text>
              ) : (
                <Text color="gray">{"\u25CB"} </Text>
              )}
              <Text
                color={
                  agent.status === "running"
                    ? "yellow"
                    : agent.status === "done"
                    ? "green"
                    : "gray"
                }
                bold
              >
                [{agent.name}]
              </Text>
            </Box>
            {agent.steps.map((step, i) => (
              <Box key={i} paddingLeft={3}>
                <Text color="gray">{"\u251C\u2500"} </Text>
                <Text color="blue">{step.tool}</Text>
                <Text> </Text>
                {step.route === "accepted" && (
                  <Text color="green">{"\u2705"}</Text>
                )}
                {step.route === "escalated" && (
                  <Text color="yellow">{"\u2B06\uFE0F"}</Text>
                )}
                {step.route === "running" && (
                  <Text color="yellow">
                    <Spinner type="dots" />
                  </Text>
                )}
                {step.route === "pending" && (
                  <Text color="gray">{"\u25CB"}</Text>
                )}
              </Box>
            ))}
          </Box>
        ))}
      </Box>
      <Box marginTop={1}>
        <Text color="gray">Progress: </Text>
        <Text color="cyan">
          {"\u2588".repeat(Math.round(progress / 5))}
          {"\u2591".repeat(20 - Math.round(progress / 5))}
        </Text>
        <Text color="white" bold>
          {" "}
          {progress.toFixed(0)}%
        </Text>
      </Box>
    </Box>
  );
}
