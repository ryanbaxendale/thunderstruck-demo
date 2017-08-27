const pythonshell = require('python-shell');
exports.helloWorld = function helloWorld(req, res) {
    pythonshell.run('worker.py', function (err, results) {
	if (err) throw err;
	res.status(200).send(results);
    });
};
