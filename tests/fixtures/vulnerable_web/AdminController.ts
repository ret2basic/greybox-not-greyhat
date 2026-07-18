import { Controller, Get, Post } from "@nestjs/common";

@Controller("internal")
export class AdminController {
  @Get("metrics")
  metrics() {}

  @Post("rotate")
  rotate() {}
}
