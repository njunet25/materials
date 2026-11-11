import { createServer } from 'node:http';
import { Readable } from 'node:stream';
import { pipeline } from 'node:stream/promises';
import { setTimeout as delay } from 'node:timers/promises';

const largeBody = Buffer.alloc(1024 * 1024, 'x');
const chunk = Buffer.alloc(64 * 1024, 'x');
const streamChunks = 256;

async function* pacedBody() {
  for (let i = 0; i < streamChunks; i++) {
    yield chunk;
    await delay(100);
  }
}

const server = createServer(async (request, response) => {
  const path = new URL(request.url, 'http://lab5.invalid').pathname;
  console.log(`${request.socket.remoteAddress} ${request.method} ${path}`);
  response.setHeader('Connection', 'close');
  response.setHeader('Cache-Control', 'no-store');
  response.setHeader('Content-Type', 'application/octet-stream');

  if (path === '/large') {
    response.setHeader('Content-Length', largeBody.length);
    response.end(largeBody);
  } else if (path === '/stream') {
    response.setHeader('Content-Length', chunk.length * streamChunks);
    try {
      await pipeline(Readable.from(pacedBody()), response);
    } catch (error) {
      if (error.code !== 'ERR_STREAM_PREMATURE_CLOSE' &&
          error.code !== 'ECONNRESET') {
        console.error(error.message);
      }
    }
  } else if (path === '/') {
    response.end('Lab5 HTTP server\n');
  } else {
    response.writeHead(404);
    response.end('Not found\n');
  }
});

server.on('error', (error) => {
  console.error(error.message);
  process.exitCode = 1;
});
server.listen({ port: 8000, host: '::', ipv6Only: false }, () => {
  console.log('Lab5 HTTP: port 8000; / small; /large 1 MiB; /stream 16 MiB (~26 s)');
});
