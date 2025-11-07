#!/bin/bash

# Script to deprecate incorrect 5.0.x versions of @cascadeflow/n8n-nodes-cascadeflow
# Run this AFTER publishing v0.5.0 to npm

echo "Deprecating versions 5.0.1 through 5.0.7..."
echo ""
echo "⚠️  Make sure you are authenticated to npm with the correct account"
echo "⚠️  Run: npm whoami"
echo ""
read -p "Press Enter to continue or Ctrl+C to cancel..."

# Deprecate each version
npm deprecate @cascadeflow/n8n-nodes-cascadeflow@5.0.1 "Version numbering error. Please uninstall and install v0.5.0 or later. See: https://github.com/lemony-ai/cascadeflow/tree/main/packages/integrations/n8n#version-migration"

npm deprecate @cascadeflow/n8n-nodes-cascadeflow@5.0.2 "Version numbering error. Please uninstall and install v0.5.0 or later. See: https://github.com/lemony-ai/cascadeflow/tree/main/packages/integrations/n8n#version-migration"

npm deprecate @cascadeflow/n8n-nodes-cascadeflow@5.0.3 "Version numbering error. Please uninstall and install v0.5.0 or later. See: https://github.com/lemony-ai/cascadeflow/tree/main/packages/integrations/n8n#version-migration"

npm deprecate @cascadeflow/n8n-nodes-cascadeflow@5.0.4 "Version numbering error. Please uninstall and install v0.5.0 or later. See: https://github.com/lemony-ai/cascadeflow/tree/main/packages/integrations/n8n#version-migration"

npm deprecate @cascadeflow/n8n-nodes-cascadeflow@5.0.5 "Version numbering error. Please uninstall and install v0.5.0 or later. See: https://github.com/lemony-ai/cascadeflow/tree/main/packages/integrations/n8n#version-migration"

npm deprecate @cascadeflow/n8n-nodes-cascadeflow@5.0.6 "Version numbering error. Please uninstall and install v0.5.0 or later. See: https://github.com/lemony-ai/cascadeflow/tree/main/packages/integrations/n8n#version-migration"

npm deprecate @cascadeflow/n8n-nodes-cascadeflow@5.0.7 "Version numbering error. Please uninstall and install v0.5.0 or later. See: https://github.com/lemony-ai/cascadeflow/tree/main/packages/integrations/n8n#version-migration"

echo ""
echo "✅ All 5.0.x versions deprecated successfully!"
echo ""
echo "Users will see deprecation warnings when installing these versions."
echo "npm will still recommend v0.5.0 as the latest stable version."
