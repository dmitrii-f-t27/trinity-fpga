// The narrow adder must agree with the original everywhere the original is right.
`default_nettype none
`timescale 1ns/1ps
module tb_add_equiv;
  reg [31:0] ao32, am32, bo32, bm32;
  wire [31:0] r_off, r_m;
  tef_add #(.OFFSET_MAX(80), .MANT_ONE(512), .SIG_BITS(10)) u_ref
    (.a_off(ao32), .a_mant(am32), .b_off(bo32), .b_mant(bm32), .out_off(r_off), .out_mant(r_m));

  reg [6:0] ao, bo; reg [8:0] am, bm;
  wire [6:0] w_off; wire [8:0] w_m;
  tef_add_w #(.MANT_W(9), .OFF_W(7), .OFFSET_MAX(80)) u_w
    (.a_off(ao), .a_mant(am), .b_off(bo), .b_mant(bm), .out_off(w_off), .out_mant(w_m));

  integer x,y,p,q, errors, checks;
  task cmp(input integer x_, input integer y_, input integer p_, input integer q_);
    begin
      ao32=x_; bo32=y_; am32=p_; bm32=q_;
      ao=x_[6:0]; bo=y_[6:0]; am=p_[8:0]; bm=q_[8:0];
      #1; checks=checks+1;
      if (r_off[6:0]!==w_off || r_m[8:0]!==w_m) begin
        errors=errors+1;
        if (errors<=10) $display("  MISMATCH off=(%0d,%0d) m=(%0d,%0d): ref=(%0d,%0d) w=(%0d,%0d)",
                                 x_,y_,p_,q_, r_off,r_m, w_off,w_m);
      end
    end
  endtask
  initial begin
    errors=0; checks=0;
    for (x=0; x<=80; x=x+4)
      for (y=0; y<=80; y=y+4)
        for (p=0; p<512; p=p+37)
          for (q=0; q<512; q=q+53)
            cmp(x,y,p,q);
    for (p=0; p<512; p=p+1)
      for (q=0; q<512; q=q+64)
        cmp(40,40,p,q);
    $display("  %0d combinations, %0d mismatches -> %s", checks, errors, errors==0?"EQUIVALENT":"NOT EQUIVALENT");
    $finish;
  end
endmodule
