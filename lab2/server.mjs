#!/usr/bin/env node

import { createReadStream } from 'node:fs';
import { readFile, realpath, stat } from 'node:fs/promises';
import { createServer as createHttpServer } from 'node:http';
import { createSecureServer as createHttp2Server } from 'node:http2';
import { dirname, extname, isAbsolute, relative, resolve, sep } from 'node:path';
import { setTimeout as delay } from 'node:timers/promises';
import { fileURLToPath } from 'node:url';
import { parseArgs } from 'node:util';

const { values: options } = parseArgs({
  options: {
    http2: { type: 'boolean', default: false },
    'no-keep-alive': { type: 'boolean', default: false },
    key: { type: 'string' },
    cert: { type: 'string' },
  },
});

if (options.http2 && options['no-keep-alive']) {
  throw new Error('--no-keep-alive cannot be used with --http2');
}
if (options.http2 && (!options.key || !options.cert)) {
  throw new Error('HTTP/2 requires --key <key.pem> and --cert <cert.pem>');
}
if (!options.http2 && (options.key || options.cert)) {
  throw new Error('--key and --cert require --http2');
}

const HOST = process.env.HOST || '127.0.0.1';
const PORT = parsePort(process.env.PORT || '3000');
const REQUEST_DELAY_MS = 100;
const STATIC_ROOT = await realpath(
  resolve(dirname(fileURLToPath(import.meta.url)), 'static'),
);

const MIME_TYPES = new Map([
  ['.css', 'text/css; charset=utf-8'],
  ['.gif', 'image/gif'],
  ['.htm', 'text/html; charset=utf-8'],
  ['.html', 'text/html; charset=utf-8'],
  ['.ico', 'image/x-icon'],
  ['.jpeg', 'image/jpeg'],
  ['.jpg', 'image/jpeg'],
  ['.js', 'text/javascript; charset=utf-8'],
  ['.json', 'application/json; charset=utf-8'],
  ['.mjs', 'text/javascript; charset=utf-8'],
  ['.png', 'image/png'],
  ['.svg', 'image/svg+xml; charset=utf-8'],
  ['.txt', 'text/plain; charset=utf-8'],
  ['.webp', 'image/webp'],
  ['.woff', 'font/woff'],
  ['.woff2', 'font/woff2'],
]);

function parsePort(value) {
  const port = Number(value);

  if (!Number.isInteger(port) || port < 0 || port > 65_535) {
    throw new Error(`Invalid PORT: ${value}`);
  }

  return port;
}

function send(res, statusCode, message, headers = {}) {
  const body = Buffer.from(message);

  res.writeHead(statusCode, {
    'content-type': 'text/plain; charset=utf-8',
    'content-length': body.length,
    ...headers,
  });
  res.end(body);
}

function isInsideStaticRoot(path) {
  const pathFromRoot = relative(STATIC_ROOT, path);

  return (
    pathFromRoot === '' ||
    (pathFromRoot !== '..' &&
      !pathFromRoot.startsWith(`..${sep}`) &&
      !isAbsolute(pathFromRoot))
  );
}

async function findStaticFile(url) {
  let pathname;

  try {
    pathname = decodeURIComponent(new URL(url, 'http://localhost').pathname);
  } catch {
    return { statusCode: 400, message: 'Bad Request\n' };
  }

  if (pathname.includes('\0')) {
    return { statusCode: 400, message: 'Bad Request\n' };
  }

  const unresolvedPath = resolve(STATIC_ROOT, `.${pathname}`);
  if (!isInsideStaticRoot(unresolvedPath)) {
    return { statusCode: 403, message: 'Forbidden\n' };
  }

  try {
    let filePath = await realpath(unresolvedPath);
    let fileStats = await stat(filePath);

    if (!isInsideStaticRoot(filePath)) {
      return { statusCode: 403, message: 'Forbidden\n' };
    }

    if (fileStats.isDirectory()) {
      filePath = await realpath(resolve(filePath, 'index.html'));
      fileStats = await stat(filePath);

      if (!isInsideStaticRoot(filePath)) {
        return { statusCode: 403, message: 'Forbidden\n' };
      }
    }

    if (!fileStats.isFile()) {
      return { statusCode: 404, message: 'Not Found\n' };
    }

    return { filePath, fileStats };
  } catch (error) {
    if (error?.code === 'ENOENT' || error?.code === 'ENOTDIR') {
      return { statusCode: 404, message: 'Not Found\n' };
    }

    throw error;
  }
}

async function handleRequest(req, res) {
  try {
    if (options['no-keep-alive']) {
      res.setHeader('connection', 'close');
    }

    await delay(REQUEST_DELAY_MS);

    if (req.method !== 'GET' && req.method !== 'HEAD') {
      send(res, 405, 'Method Not Allowed\n', { allow: 'GET, HEAD' });
      return;
    }

    const result = await findStaticFile(req.url || '/');
    if (!result.filePath) {
      send(res, result.statusCode, result.message);
      return;
    }

    res.writeHead(200, {
      'content-type':
        MIME_TYPES.get(extname(result.filePath).toLowerCase()) ||
        'application/octet-stream',
      'content-length': result.fileStats.size,
      'x-content-type-options': 'nosniff',
    });

    if (req.method === 'HEAD') {
      res.end();
      return;
    }

    const fileStream = createReadStream(result.filePath);
    fileStream.on('error', (error) => {
      console.error('Failed to read static file:', error);
      res.destroy(error);
    });
    fileStream.pipe(res);
  } catch (error) {
    console.error('Failed to handle request:', error);

    if (!res.headersSent) {
      send(res, 500, 'Internal Server Error\n');
    } else {
      res.destroy(error);
    }
  }
}

const server = options.http2
  ? createHttp2Server(
      {
        key: await readFile(options.key),
        cert: await readFile(options.cert),
      },
      handleRequest,
    )
  : createHttpServer(handleRequest);

server.on('error', (error) => {
  console.error('Server error:', error);
  process.exitCode = 1;
});

server.listen(PORT, HOST, () => {
  const address = server.address();
  const port = typeof address === 'object' && address ? address.port : PORT;
  const protocol = options.http2 ? 'HTTP/2' : 'HTTP/1.1';
  const scheme = options.http2 ? 'https' : 'http';
  const host = HOST.includes(':') ? `[${HOST}]` : HOST;

  console.log(
    `${protocol} static server listening on ${scheme}://${host}:${port}`,
  );
  if (options['no-keep-alive']) {
    console.log('HTTP/1.1 keep-alive disabled: closing each connection after its response');
  }
});
