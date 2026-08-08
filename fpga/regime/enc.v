`default_nettype none
// Кодеры поля режима: exponent -> (длина кодового слова, поле режима).
// Зеркало декодеров: считаем ту же цену с другой стороны.

module enc_unary #(parameter integer ES=2)
  (input wire signed [8:0] e, output wire [4:0] k, output wire [15:0] f);
  wire [8:0] a = e[8] ? -e : e;
  assign k = a[8:ES];                       // просто сдвиг
  assign f = e[8] ? ~(16'hFFFF << k) : (16'hFFFF << (5'd16-k));
endmodule

module enc_log (input wire signed [8:0] e, output wire [4:0] k, output wire [15:0] f);
  wire [8:0] a = e[8] ? -e : e;
  reg [3:0] msb; integer i;                 // позиция старшей единицы = LZC
  always @(*) begin msb = 0;
    for (i = 0; i < 9; i = i+1) if (a[i]) msb = i[3:0]; end
  assign k = {1'b0, msb};
  assign f = {msb[2:0], a[7:0], 5'b0};
endmodule

module enc_sqrt (input wire signed [8:0] e, output wire [4:0] k, output wire [15:0] f);
  wire [8:0] a = e[8] ? -e : e;
  reg [4:0] r; integer i;                   // целочисленный корень: ceil(sqrt(a))
  always @(*) begin r = 0;
    for (i = 1; i <= 22; i = i+1) if (i*i < a) r = i[4:0]+1'b1; end
  assign k = r;
  assign f = e[8] ? ~(16'hFFFF << r) : (16'hFFFF << (5'd16-r));
endmodule
