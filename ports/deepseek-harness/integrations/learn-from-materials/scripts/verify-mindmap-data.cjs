// Compatibility entry point: maintained tests execute the production renderer.
// Memory geometry checks do not establish browser paint or semantic acceptance.
const {spawnSync}=require('node:child_process');
const path=require('node:path');
const result=spawnSync(process.execPath,['--test',path.join(__dirname,'tests/test-framework-layout.cjs')],{stdio:'inherit'});
if(result.error){console.error(result.error.message);process.exit(2);}
process.exit(result.status===null?2:result.status);
