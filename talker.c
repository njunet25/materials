#include <stdlib.h>
#include <stdio.h>
#include <stdint.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <arpa/inet.h>
#include <poll.h>
#include <errno.h>
#include <unistd.h>
#define HELP "usage: %s local_ip local_port peer_ip peer_port send_seq recv_seq\n"
#define BAIL(handle) {perror(handle); return 1;}

static int read_port(const char *text, unsigned short *port) {
    char *end;
    unsigned long value = strtoul(text, &end, 10);
    if (*end != '\0' || value == 0 || value > UINT16_MAX)
        return -1;

    *port = (unsigned short)value;
    return 0;
}

static int read_seq(const char *text, uint32_t *seq) {
    char *end;
    unsigned long long value = strtoull(text, &end, 10);
    if (end == text || *end != '\0' || value > UINT32_MAX)
        return -1;

    *seq = (uint32_t)value;
    return 0;
}

int main(int argc, char **argv) {
    if (argc != 7) {
        printf(HELP, argv[0]);
        return 1;
    }
    struct sockaddr_in local = {.sin_family = AF_INET};
    struct sockaddr_in peer = {.sin_family = AF_INET};

    if (inet_pton(AF_INET, argv[1], &local.sin_addr) != 1)
        BAIL("inet_pton(local_ip)");

    if (inet_pton(AF_INET, argv[3], &peer.sin_addr) != 1)
        BAIL("inet_pton(peer_ip)");

    unsigned short local_port, peer_port;
    if (read_port(argv[2], &local_port) != 0) {
        fprintf(stderr, "Invalid local port (expected 1-65535): %s\n", argv[2]);
        return 1;
    }
    if (read_port(argv[4], &peer_port) != 0) {
        fprintf(stderr, "Invalid peer port (expected 1-65535): %s\n", argv[4]);
        return 1;
    }

    local.sin_port = htons(local_port);
    peer.sin_port = htons(peer_port);
    
    uint32_t send_seq, recv_seq;
    if (read_seq(argv[5], &send_seq) != 0) {
        fprintf(stderr, "Invalid send sequence: %s\n", argv[5]);
        return 1;
    }
    if (read_seq(argv[6], &recv_seq) != 0) {
        fprintf(stderr, "Invalid receive sequence: %s\n", argv[6]);
        return 1;
    }

    // Create TCP connection without actually connecting.

    int fd;
    if ((fd = socket(AF_INET, SOCK_STREAM, 0)) < 0) BAIL("socket");

    int repair = TCP_REPAIR_ON;
    if (setsockopt(fd, SOL_TCP, TCP_REPAIR, &repair, sizeof(repair)) < 0) BAIL("setsockopt(TCP_REPAIR_ON)");

    if (bind(fd, (struct sockaddr *)&local, sizeof(struct sockaddr_in)) < 0) BAIL("bind");

    // Set send/recv seqno
    int queue = TCP_SEND_QUEUE;
    if (setsockopt(fd, SOL_TCP, TCP_REPAIR_QUEUE, &queue, sizeof(queue))) BAIL("setsockopt(QUEUE)");
    if (setsockopt(fd, SOL_TCP, TCP_QUEUE_SEQ, &send_seq, sizeof(send_seq))) BAIL("setsockopt(send_seq)");

    queue = TCP_RECV_QUEUE;
    if (setsockopt(fd, SOL_TCP, TCP_REPAIR_QUEUE, &queue, sizeof(queue))) BAIL("setsockopt(QUEUE)");
    if (setsockopt(fd, SOL_TCP, TCP_QUEUE_SEQ, &recv_seq, sizeof(recv_seq))) BAIL("setsockopt(recv_seq)");

    // Set peer
    if (connect(fd, (struct sockaddr *)&peer, sizeof(struct sockaddr_in)) < 0) BAIL("connect");

    // Exit repairing, and use as normal.
    repair = TCP_REPAIR_OFF_NO_WP;
    if (setsockopt(fd, SOL_TCP, TCP_REPAIR, &repair, sizeof(repair)) < 0) BAIL("setsockopt(TCP_REPAIR_OFF)");
    struct pollfd fds[2] = {
        {.fd = STDIN_FILENO, .events = POLLIN},
        {.fd = fd,          .events = POLLIN},
    };
    char buf[4096];

    for (;;) {
        if (poll(fds, 2, -1) < 0) {
            if (errno == EINTR) continue;
            BAIL("poll");
        }

        for (int i = 0; i < 2; i++) {
            if (!(fds[i].revents &
                (POLLIN | POLLHUP | POLLERR | POLLNVAL)))
                continue;

            ssize_t n = read(fds[i].fd, buf, sizeof(buf));
            if (n < 0) {
                if (errno == EINTR) continue;
                BAIL("read");
            }
            if (n == 0) {
                if (i == 1) goto done;
                if (shutdown(fd, SHUT_WR) < 0) BAIL("shutdown");
                fds[0].fd = -1;
                continue;
            }

            for (ssize_t off = 0; off < n;) {
                ssize_t m = i == 0
                    ? send(fd, buf + off, n - off, MSG_NOSIGNAL)
                    : write(STDOUT_FILENO, buf + off, n - off);
                if (m < 0) {
                    if (errno == EINTR) continue;
                    BAIL("write");
                }
                if (m == 0) goto done;
                off += m;
            }
        }
        
    }
done:
    close(fd);

    return 0;
}
