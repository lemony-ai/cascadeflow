import React from "react";
import { render, Box, Text } from "ink";

function App() {
	return (
		<Box flexDirection="column" alignItems="center" padding={1}>
			<Box borderStyle="double" borderColor="cyan" paddingX={3} paddingY={1}>
				<Text bold color="cyan">
					CascadeFlow Demo
				</Text>
			</Box>
			<Box marginTop={1}>
				<Text dimColor>Intelligent LLM Routing & Orchestration</Text>
			</Box>
		</Box>
	);
}

render(<App />);
