import { crc32 } from "node:zlib";

/** A valid 1 × 1 grey PNG, built for the tests; not a receipt. */
const GREY_PIXEL = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAAAAAA6fptVAAAACklEQVR4nGNoAAAAggCBd81ytgAAAABJRU5ErkJggg==",
  "base64",
);
const IEND_LENGTH = 12;

/**
 * The grey PNG with a `tEXt` chunk holding `tag`, so each run imports an image with a new
 * hash that a browser can still show (the fake reader returns its fixed receipt for any
 * image).
 */
export function syntheticPng(tag: string): Buffer {
  const type = Buffer.from("tEXt", "latin1");
  const data = Buffer.from(`Comment\0${tag}`, "latin1");
  const length = Buffer.alloc(4);
  length.writeUInt32BE(data.length);
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(Buffer.concat([type, data])));
  const end = GREY_PIXEL.length - IEND_LENGTH;
  return Buffer.concat([
    GREY_PIXEL.subarray(0, end),
    length,
    type,
    data,
    crc,
    GREY_PIXEL.subarray(end),
  ]);
}
