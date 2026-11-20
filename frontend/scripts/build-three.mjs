import {build} from "esbuild";
import {fileURLToPath} from "node:url";
const root=fileURLToPath(new URL("../../",import.meta.url));
await build({entryPoints:[root+"skills/3d-motion-infographic/runtime/scene.js"],
  outfile:root+"skills/3d-motion-infographic/runtime/three-scene.js",bundle:true,format:"iife",minify:true,
  target:"chrome110",legalComments:"eof",absWorkingDir:root+"frontend",
  nodePaths:[root+"frontend/node_modules"]});
