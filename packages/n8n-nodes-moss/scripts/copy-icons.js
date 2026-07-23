const fs = require('fs');
const path = require('path');

function copyDirFiltered(srcDir, destDir, predicate) {
	if (!fs.existsSync(srcDir)) {
		throw new Error(`Required asset directory missing: ${srcDir}`);
	}
	fs.mkdirSync(destDir, { recursive: true });
	let copied = 0;
	for (const file of fs.readdirSync(srcDir)) {
		const src = path.join(srcDir, file);
		if (!fs.statSync(src).isFile()) continue;
		if (!predicate(file)) continue;
		fs.copyFileSync(src, path.join(destDir, file));
		copied += 1;
	}
	if (copied === 0) {
		throw new Error(`No matching assets found in ${srcDir}`);
	}
}

const root = path.join(__dirname, '..');

copyDirFiltered(
	path.join(root, 'nodes', 'Moss'),
	path.join(root, 'dist', 'nodes', 'Moss'),
	(file) => file.endsWith('.svg') || file.endsWith('.png') || file.endsWith('.json'),
);

copyDirFiltered(
	path.join(root, 'icons'),
	path.join(root, 'dist', 'icons'),
	(file) => file.endsWith('.svg') || file.endsWith('.png'),
);

console.log('Copied Moss node icons and metadata');
